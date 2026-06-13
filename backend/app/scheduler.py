"""Background task that re-evaluates each subscribed, auto-charge-enabled user's
threshold against the current Nord Pool price and triggers start/stop accordingly.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import prices, tesla
from .config import get_settings
from .db import SessionLocal
from .models import ChargeEvent, Subscription, TeslaAccount, User
from .notifications import send_push_notification

log = logging.getLogger(__name__)


async def _evaluate_user_hourly(session, user: User, now: datetime, prev_hour: datetime) -> None:
    if not user.region or user.threshold_price is None:
        return
    if user.tesla is None or not user.tesla.vehicle_id:
        return

    try:
        current_data = await prices.current_price(user.region, now)
        prev_data = await prices.current_price(user.region, prev_hour)
        current_val = current_data["price"]
        prev_val = prev_data["price"]
        if user.vat_included:
            multiplier = prices.get_vat_multiplier(user.region)
            current_val *= multiplier
            prev_val *= multiplier
    except Exception as e:
        log.warning("price fetch failed for user=%s: %s", user.id, e)
        return

    threshold = float(user.threshold_price)
    was_cheap = prev_val <= threshold
    is_cheap = current_val <= threshold

    # If the price didn't cross the threshold, we do nothing to save API calls
    if was_cheap == is_cheap:
        return

    # Price crossed the threshold!
    try:
        token = await tesla.get_access_token(session, user)
        state = await tesla.vehicle_data(token, user.tesla.vehicle_id)
    except ValueError:
        log.info("vehicle asleep for user=%s, attempting to wake", user.id)
        try:
            await tesla.wake_up(token, user.tesla.vehicle_id)
            for _ in range(6):
                await asyncio.sleep(5)
                try:
                    state = await tesla.vehicle_data(token, user.tesla.vehicle_id)
                    break
                except ValueError:
                    pass
            else:
                log.info("vehicle failed to wake for user=%s", user.id)
                return
        except Exception as e:
            log.warning("failed to wake vehicle for user=%s: %s", user.id, e)
            return
    except Exception as e:
        log.warning("vehicle_data failed for user=%s: %s", user.id, e)
        return

    resp = (state or {}).get("response") or {}
    charge_data = resp.get("charge_state") or resp
    location_data = resp.get("drive_state") or {}

    # Check geofence if home location is set
    if user.home_latitude is not None and user.home_longitude is not None:
        veh_lat = location_data.get("latitude")
        veh_lon = location_data.get("longitude")
        if veh_lat is not None and veh_lon is not None:
            lat_diff = (veh_lat - float(user.home_latitude)) * 111000
            lon_diff = (veh_lon - float(user.home_longitude)) * 111000 * math.cos(math.radians(float(user.home_latitude)))
            distance_meters = math.sqrt(lat_diff**2 + lon_diff**2)
            if distance_meters > 200:
                log.info("user=%s vehicle is not at home (distance: %.0fm)", user.id, distance_meters)
                return
    else:
        log.info("user=%s has no home location set, skipping auto-charge", user.id)
        return

    charging_state = charge_data.get("charging_state")
    plugged_in = charging_state and charging_state != "Disconnected"
    currently_charging = charging_state == "Charging"

    if not plugged_in:
        log.info("user=%s vehicle unplugged, skipping", user.id)
        return

    is_pro = user.subscription and user.subscription.active
    auto_charge = user.auto_charge_enabled and is_pro

    action = "skip"
    detail = None

    if is_cheap and not was_cheap:
        # Price dropped
        msg_title = "Electricity Price Dropped"
        msg_body = f"Price is now {current_val:.4f} {user.currency}/kWh. "
        if auto_charge and not currently_charging:
            try:
                await tesla.charge_start(token, user.tesla.vehicle_id)
                action = "start"
                msg_body += "Auto-charging started."
            except Exception as e:
                detail = f"start failed: {e!s:.200}"
                msg_body += "Failed to auto-start charging."
        elif currently_charging:
            msg_body += "Vehicle is already charging."
        else:
            msg_body += "Vehicle is plugged in."
            
        if user.push_token and user.price_change_reminder:
            asyncio.create_task(send_push_notification(user.push_token, msg_title, msg_body))

    elif was_cheap and not is_cheap:
        # Price rose
        msg_title = "Electricity Price Rose"
        msg_body = f"Price is now {current_val:.4f} {user.currency}/kWh. "
        if auto_charge and currently_charging:
            try:
                await tesla.charge_stop(token, user.tesla.vehicle_id)
                action = "stop"
                msg_body += "Auto-charging stopped."
            except Exception as e:
                detail = f"stop failed: {e!s:.200}"
                msg_body += "Failed to auto-stop charging."
        elif not currently_charging:
            msg_body += "Vehicle is not charging."
        else:
            msg_body += "Please stop charging manually."

        if user.push_token and user.price_change_reminder:
            asyncio.create_task(send_push_notification(user.push_token, msg_title, msg_body))

    if action != "skip" or detail is not None:
        session.add(
            ChargeEvent(
                user_id=user.id,
                action=action,
                price=current_val,
                threshold=threshold,
                detail=detail,
            )
        )
        await session.commit()


async def _evaluate_all_users() -> None:
    now = datetime.now(timezone.utc)
    prev_hour = now - timedelta(hours=1)
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.threshold_price.is_not(None))
            .options(selectinload(User.tesla), selectinload(User.subscription))
        )
        users = result.scalars().unique().all()
        for user in users:
            try:
                await _evaluate_user_hourly(session, user, now, prev_hour)
            except Exception as e:
                log.exception("evaluate_user failed: %s", e)


async def run_forever() -> None:
    log.info("hourly scheduler running")
    last_evaluated_hour = None
    while True:
        now = datetime.now(timezone.utc)
        if last_evaluated_hour is not None and last_evaluated_hour != now.hour:
            try:
                await _evaluate_all_users()
            except Exception:
                log.exception("scheduler tick failed")
        last_evaluated_hour = now.hour
        await asyncio.sleep(60)


async def fetch_daily_prices_forever() -> None:
    log.info("price fetcher scheduler running")
    last_fetched_date = None
    while True:
        now = datetime.now(timezone.utc)
        # 15:00 EEST is UTC+3 in summer, UTC+2 in winter. 12:00 UTC covers both.
        # Run between 12:00 and 13:00 UTC
        if now.hour == 12 and last_fetched_date != now.date():
            try:
                async with SessionLocal() as session:
                    # Nord Pool day-ahead prices for tomorrow are published around 13:00 CET/CEST
                    target_date = now + timedelta(days=1)
                    await prices.fetch_and_store_prices(session, target_date)
                last_fetched_date = now.date()
                log.info("Successfully fetched prices for %s", target_date.date())
            except Exception as e:
                log.exception("price fetch failed: %s", e)
        
        # Check every 10 minutes
        await asyncio.sleep(600)
