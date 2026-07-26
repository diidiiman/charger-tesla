import asyncio
import logging
import zoneinfo
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from . import prices, tesla
from .db import SessionLocal
from .models import Subscription, User
from .schedule_calculator import ScheduleCalculator
from .tesla_schedule_manager import TeslaScheduleManager

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

async def sync_charge_schedule(session: AsyncSession, user: User, now: datetime = None, target_date: datetime.date = None) -> None:
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

    tz_str = REGION_TIMEZONES.get(user.region, "UTC") if user.region else "UTC"
    tz = zoneinfo.ZoneInfo(tz_str)
    now_local = now.astimezone(tz)

    tesla_manager = TeslaScheduleManager(token, user.tesla.vehicle_id)

    if not auto_charge or user.threshold_price is None or not user.region or user.home_latitude is None or user.home_longitude is None:
        await tesla_manager.clear_all_schedules()
        return

    if target_date is not None:
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
        end_time = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=tz)
    else:
        start_time = now.replace(minute=0, second=0, microsecond=0)
        end_time = (now + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

    stmt = select(prices.RegionPrice).where(
        prices.RegionPrice.region == user.region,
        prices.RegionPrice.valid_from >= start_time,
        prices.RegionPrice.valid_to <= end_time
    ).order_by(prices.RegionPrice.valid_from)
    
    result = await session.execute(stmt)
    region_prices = result.scalars().all()

    multiplier = prices.get_vat_multiplier(user.region) if user.vat_included else 1.0
    threshold = float(user.threshold_price)

    cheap_hours = ScheduleCalculator.get_cheap_prices(region_prices, threshold, multiplier)
    blocks = ScheduleCalculator.group_into_blocks(cheap_hours, tz)
    desired_blocks = ScheduleCalculator.blocks_to_time_windows(blocks, tz, now_local, target_date)

    try:
        sched_list = await tesla_manager.fetch_schedules()
        
        schedules_to_delete, schedules_to_update = TeslaScheduleManager.calculate_schedule_changes(
            sched_list, target_date, now_local, float(user.home_latitude), float(user.home_longitude)
        )

        await tesla_manager.execute_deletions(schedules_to_delete)
        await tesla_manager.execute_updates(schedules_to_update)
        await tesla_manager.execute_additions(desired_blocks, sched_list, user, threshold)

    except Exception as e:
        log.warning("failed to sync schedules for user=%s: %s", user.id, e)


async def _sync_all_users(session: AsyncSession, target_date: datetime.date = None) -> None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(User)
        .where(User.auto_charge_enabled == True)
        .options(selectinload(User.tesla), selectinload(User.subscription))
    )
    users = result.scalars().unique().all()
    for user in users:
        try:
            await sync_charge_schedule(session, user, now, target_date)
        except Exception as e:
            log.exception("sync_charge_schedule failed for user %s: %s", user.id, e)


async def fetch_daily_prices_forever() -> None:
    log.info("price fetcher scheduler running")
    last_fetched_date = None
    while True:
        now = datetime.now(timezone.utc)
        if now.hour >= 12 and last_fetched_date != now.date():
            try:
                async with SessionLocal() as session:
                    target_date = now + timedelta(days=1)
                    await prices.fetch_and_store_prices(session, target_date)
                    await _sync_all_users(session, target_date.date())
                    
                last_fetched_date = now.date()
                log.info("Successfully fetched prices and synced schedules for %s", target_date.date())
            except Exception as e:
                log.exception("price fetch failed: %s", e)

        await asyncio.sleep(600)


async def verify_expired_subscriptions_forever() -> None:
    log.info("subscription verification scheduler running")
    last_run_date = None
    while True:
        now = datetime.now(timezone.utc)
        if now.hour == 2 and last_run_date != now.date():
            try:
                from .subscriptions import verify_receipt
                
                async with SessionLocal() as session:
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
                                    await sync_charge_schedule(session, sub.user, now)
                                
                        except Exception as e:
                            log.warning("Failed to re-verify subscription for user_id=%s: %s", sub.user_id, e)
                            
                        await asyncio.sleep(1)
                        
                    await session.commit()
                last_run_date = now.date()
                log.info("Successfully ran daily subscription verification sweep")
            except Exception as e:
                log.exception("Subscription verification sweep failed: %s", e)

        await asyncio.sleep(600)
