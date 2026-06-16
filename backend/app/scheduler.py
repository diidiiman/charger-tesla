import asyncio
import logging
import math
import zoneinfo
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from . import prices, tesla
from .config import get_settings
from .db import SessionLocal
from .models import Subscription, User
from .notifications import send_push_notification

log = logging.getLogger(__name__)

REGION_TIMEZONES = {
    "EE": "Europe/Tallinn",
    "FI": "Europe/Helsinki",
    "LT": "Europe/Vilnius",
    "LV": "Europe/Riga",
    "SE1": "Europe/Stockholm",
    "SE2": "Europe/Stockholm",
    "SE3": "Europe/Stockholm",
    "SE4": "Europe/Stockholm",
    "NO1": "Europe/Oslo",
    "NO2": "Europe/Oslo",
    "NO3": "Europe/Oslo",
    "NO4": "Europe/Oslo",
    "NO5": "Europe/Oslo",
    "DK1": "Europe/Copenhagen",
    "DK2": "Europe/Copenhagen",
    "AT": "Europe/Vienna",
    "BE": "Europe/Brussels",
    "DE-LU": "Europe/Berlin",
    "FR": "Europe/Paris",
    "NL": "Europe/Amsterdam",
}

async def sync_charge_schedule(session, user: User, now: datetime = None) -> None:
    if now is None:
        now = datetime.now(timezone.utc)

    is_pro = user.subscription and user.subscription.active
    auto_charge = user.auto_charge_enabled and is_pro

    if not user.tesla or not user.tesla.vehicle_id:
        return

    try:
        token = await tesla.get_access_token(session, user)
    except Exception as e:
        log.warning("failed to get token for user=%s: %s", user.id, e)
        return

    # 1. Clear existing schedules if downgraded or missing data
    if not auto_charge or user.threshold_price is None or not user.region or user.home_latitude is None or user.home_longitude is None:
        try:
            schedules = await tesla.get_charge_schedules(token, user.tesla.vehicle_id)
            sched_list = schedules if isinstance(schedules, list) else ([{"id": int(k)} for k in schedules.keys()] if isinstance(schedules, dict) else [])
            if sched_list:
                try:
                    await tesla.wake_up(token, user.tesla.vehicle_id)
                    await asyncio.sleep(5)
                except Exception:
                    pass
                for sched in sched_list:
                    if "id" in sched:
                        await tesla.remove_charge_schedule(token, user.tesla.vehicle_id, int(sched["id"]))
        except Exception as e:
            log.warning("failed to clear schedules for user=%s: %s", user.id, e)
        return

    # 2. Fetch prices from now until end of tomorrow
    tomorrow_end = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    stmt = select(prices.RegionPrice).where(
        prices.RegionPrice.region == user.region,
        prices.RegionPrice.valid_from >= now.replace(minute=0, second=0, microsecond=0),
        prices.RegionPrice.valid_to <= tomorrow_end
    ).order_by(prices.RegionPrice.valid_from)
    
    result = await session.execute(stmt)
    region_prices = result.scalars().all()

    # Apply VAT and threshold
    multiplier = prices.get_vat_multiplier(user.region) if user.vat_included else 1.0
    threshold = float(user.threshold_price)

    cheap_hours = []
    for p in region_prices:
        val = float(p.price) * multiplier
        if val <= threshold:
            cheap_hours.append(p)

    # 3. Group into contiguous blocks, splitting at midnight local time
    blocks = []
    if cheap_hours:
        tz_str = REGION_TIMEZONES.get(user.region, "UTC")
        tz = zoneinfo.ZoneInfo(tz_str)
        
        current_block = [cheap_hours[0]]
        for i in range(1, len(cheap_hours)):
            prev = current_block[-1]
            curr = cheap_hours[i]
            
            prev_local = prev.valid_from.astimezone(tz)
            curr_local = curr.valid_from.astimezone(tz)
            
            if curr.valid_from == prev.valid_to and prev_local.date() == curr_local.date():
                current_block.append(curr)
            else:
                blocks.append(current_block)
                current_block = [curr]
        blocks.append(current_block)

    # 4. Clear existing schedules and send new ones
    try:
        schedules = await tesla.get_charge_schedules(token, user.tesla.vehicle_id)
        sched_list = schedules if isinstance(schedules, list) else ([{"id": int(k)} for k in schedules.keys()] if isinstance(schedules, dict) else [])
        if sched_list:
            try:
                await tesla.wake_up(token, user.tesla.vehicle_id)
                await asyncio.sleep(5)
            except Exception:
                pass
            for sched in sched_list:
                if "id" in sched:
                    await tesla.remove_charge_schedule(token, user.tesla.vehicle_id, int(sched["id"]))
        
        if not blocks:
            return
            
        # If we have blocks to send, wake the car up
        if not sched_list:
            try:
                await tesla.wake_up(token, user.tesla.vehicle_id)
                await asyncio.sleep(5)
            except Exception:
                pass

        tz_str = REGION_TIMEZONES.get(user.region, "UTC")
        tz = zoneinfo.ZoneInfo(tz_str)

        for block in blocks:
            start_dt = block[0].valid_from.astimezone(tz)
            end_dt = block[-1].valid_to.astimezone(tz)

            start_minutes = start_dt.hour * 60 + start_dt.minute
            end_minutes = end_dt.hour * 60 + end_dt.minute
            
            # Tesla days_of_week mapping for string inputs
            days_map = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]
            days_of_week = days_map[start_dt.weekday()]

            await tesla.add_charge_schedule(
                access_token=token,
                vehicle_id=user.tesla.vehicle_id,
                days_of_week=days_of_week,
                enabled=True,
                lat=float(user.home_latitude),
                lon=float(user.home_longitude),
                start_time=start_minutes,
                end_time=end_minutes,
                one_time=False
            )

            if user.push_token and user.price_change_reminder:
                msg_title = "Charging Schedule Set"
                msg_body = f"Scheduled to charge on {start_dt.strftime('%A')} from {start_dt.strftime('%H:%M')} to {end_dt.strftime('%H:%M')} (Price ≤ {threshold:.4f} {user.currency}/kWh)."
                asyncio.create_task(send_push_notification(user.push_token, msg_title, msg_body))

    except Exception as e:
        log.warning("failed to sync schedules for user=%s: %s", user.id, e)

async def _sync_all_users(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(User)
        .where(User.auto_charge_enabled == True)
        .options(selectinload(User.tesla), selectinload(User.subscription))
    )
    users = result.scalars().unique().all()
    for user in users:
        try:
            await sync_charge_schedule(session, user, now)
        except Exception as e:
            log.exception("sync_charge_schedule failed for user %s: %s", user.id, e)


async def fetch_daily_prices_forever() -> None:
    log.info("price fetcher scheduler running")
    last_fetched_date = None
    while True:
        now = datetime.now(timezone.utc)
        # Run between 12:00 and 13:00 UTC
        if now.hour == 12 and last_fetched_date != now.date():
            try:
                async with SessionLocal() as session:
                    # Nord Pool day-ahead prices for tomorrow are published around 13:00 CET/CEST
                    target_date = now + timedelta(days=1)
                    await prices.fetch_and_store_prices(session, target_date)
                    
                    # Prices received, sync schedules for all enabled users
                    await _sync_all_users(session)
                    
                last_fetched_date = now.date()
                log.info("Successfully fetched prices and synced schedules for %s", target_date.date())
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
                        ).options(selectinload(Subscription.user))
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
                                if sub.user:
                                    sub.user.auto_charge_enabled = False
                                    # Clear schedule
                                    await sync_charge_schedule(session, sub.user, now)
                                
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
