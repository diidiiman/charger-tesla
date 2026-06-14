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


async def _evaluate_user(
    session, user: User, now: datetime = None
) -> None:
    if now is None:
        now = datetime.now(timezone.utc)

    is_pro = user.subscription and user.subscription.active
    auto_charge = user.auto_charge_enabled and is_pro

    if not auto_charge:
        return

    if not user.region or user.threshold_price is None:
        return
    if user.tesla is None or not user.tesla.vehicle_id:
        return

    try:
        current_data = await prices.current_price(session, user.region, now)
        current_val = current_data["price"]
        if user.vat_included:
            multiplier = prices.get_vat_multiplier(user.region)
            current_val *= multiplier
    except Exception as e:
        log.warning("price fetch failed for user=%s: %s", user.id, e)
        return

    threshold = float(user.threshold_price)
    is_cheap = current_val <= threshold

    try:
        from .models import VehicleState
        
        # Only use cached telemetry. No REST API polling.
        state_db = (
            await session.execute(
                select(VehicleState).where(VehicleState.vehicle_id == user.tesla.vehicle_vin)
            )
        ).scalar_one_or_none()
        
        if not state_db:
            return # No telemetry data
            
        charging_state = state_db.charging_state
        plugged_in = charging_state and charging_state != "Disconnected"
        currently_charging = charging_state in ("Charging", "Starting", "Preparing")

        if not plugged_in:
            return

        # Check geofence
        if user.home_latitude is not None and user.home_longitude is not None:
            if state_db.latitude is not None and state_db.longitude is not None:
                lat_diff = (float(state_db.latitude) - float(user.home_latitude)) * 111000
                lon_diff = (
                    (float(state_db.longitude) - float(user.home_longitude))
                    * 111000
                    * math.cos(math.radians(float(user.home_latitude)))
                )
                distance_meters = math.sqrt(lat_diff**2 + lon_diff**2)
                if distance_meters > 200:
                    return
            else:
                return
        else:
            return

        action = "skip"
        detail = None
        msg_title = None
        msg_body = None

        if is_cheap and not currently_charging:
            battery = state_db.battery_level or 0
            limit = state_db.charge_limit_soc or 100
            if battery < limit:
                msg_title = "Charging Started"
                msg_body = f"Price is cheap ({current_val:.4f} {user.currency}/kWh). "
                try:
                    token = await tesla.get_access_token(session, user)
                    await tesla.charge_start(token, user.tesla.vehicle_id)
                    action = "start"
                    msg_body += "Auto-charging started."
                except Exception as e:
                    detail = f"start failed: {e!s:.200}"
                    msg_body += "Failed to auto-start charging."
                
                if user.push_token and user.price_change_reminder and action == "start":
                    asyncio.create_task(send_push_notification(user.push_token, msg_title, msg_body))

        elif not is_cheap and currently_charging:
            msg_title = "Charging Stopped"
            msg_body = f"Price is expensive ({current_val:.4f} {user.currency}/kWh). "
            try:
                token = await tesla.get_access_token(session, user)
                await tesla.charge_stop(token, user.tesla.vehicle_id)
                action = "stop"
                msg_body += "Auto-charging stopped."
            except Exception as e:
                detail = f"stop failed: {e!s:.200}"
                msg_body += "Failed to auto-stop charging."
            
            if user.push_token and user.price_change_reminder and action == "stop":
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

    except Exception as e:
        log.warning("failed to evaluate vehicle state for user=%s: %s", user.id, e)
        return


async def _evaluate_all_users() -> None:
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .where(User.threshold_price.is_not(None))
            .options(selectinload(User.tesla), selectinload(User.subscription))
        )
        users = result.scalars().unique().all()
        for user in users:
            try:
                await _evaluate_user(session, user, now)
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


async def verify_expired_subscriptions_forever() -> None:
    log.info("subscription verification scheduler running")
    last_run_date = None
    while True:
        now = datetime.now(timezone.utc)
        # Run daily at 02:00 UTC
        if now.hour == 2 and last_run_date != now.date():
            try:
                from .subscriptions import verify_receipt
                
                async with SessionLocal() as session:
                    # Find all subscriptions that are marked active but have expired
                    result = await session.execute(
                        select(Subscription).where(
                            Subscription.active == True,
                            Subscription.expires_at < now
                        )
                    )
                    subs = result.scalars().all()
                    
                    for sub in subs:
                        log.info("Re-verifying expired subscription for user_id=%s platform=%s", sub.user_id, sub.platform)
                        try:
                            v_result = await verify_receipt(sub.platform, sub.receipt)
                            
                            sub.active = v_result["active"]
                            sub.expires_at = v_result["expires_at"]
                            sub.last_verified_at = now
                            
                            if not sub.active:
                                log.info("Subscription officially lapsed for user_id=%s", sub.user_id)
                                
                        except Exception as e:
                            log.warning("Failed to re-verify subscription for user_id=%s: %s", sub.user_id, e)
                            
                        # Be polite to the app stores
                        await asyncio.sleep(1)
                        
                    await session.commit()
                last_run_date = now.date()
                log.info("Successfully ran daily subscription verification sweep")
            except Exception as e:
                log.exception("Subscription verification sweep failed: %s", e)

        # Check every 10 minutes
        await asyncio.sleep(600)
