"""Background task that re-evaluates each subscribed, auto-charge-enabled user's
threshold against the current Nord Pool price and triggers start/stop accordingly.

Free users are skipped here — manual start/stop only.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import prices, tesla
from .config import get_settings
from .db import SessionLocal
from .models import ChargeEvent, Subscription, TeslaAccount, User

log = logging.getLogger(__name__)


async def _evaluate_user(session, user: User) -> None:
    if not user.region or user.threshold_price is None:
        return
    if user.tesla is None or not user.tesla.vehicle_id:
        return

    try:
        price_data = await prices.current_price(user.region)
        price_val = price_data["price"]
        if user.vat_included:
            price_val *= prices.get_vat_multiplier(user.region)
    except Exception as e:
        log.warning("price fetch failed for user=%s: %s", user.id, e)
        return

    try:
        token = await tesla.get_access_token(session, user)
        state = await tesla.charge_state(token, user.tesla.vehicle_id)
    except ValueError:
        # Vehicle is asleep, assume not charging. 
        # (Could attempt to wake if price is cheap, but would drain battery if unplugged)
        log.info("vehicle asleep for user=%s", user.id)
        return
    except Exception as e:
        log.warning("charge_state failed for user=%s: %s", user.id, e)
        return

    resp = (state or {}).get("response") or {}
    charge_data = resp.get("charge_state") or resp
    charging_state = charge_data.get("charging_state")
    plugged_in = charging_state and charging_state != "Disconnected"
    currently_charging = charging_state == "Charging"

    threshold = float(user.threshold_price)
    cheap = price_val <= threshold

    action = "skip"
    detail = None

    if not plugged_in:
        detail = f"unplugged ({charging_state})"
    elif cheap and not currently_charging:
        try:
            await tesla.charge_start(token, user.tesla.vehicle_id)
            action = "start"
        except Exception as e:
            detail = f"start failed: {e!s:.200}"
    elif (not cheap) and currently_charging:
        try:
            await tesla.charge_stop(token, user.tesla.vehicle_id)
            action = "stop"
        except Exception as e:
            detail = f"stop failed: {e!s:.200}"
    else:
        detail = f"no-op (cheap={cheap}, charging={currently_charging})"

    session.add(
        ChargeEvent(
            user_id=user.id,
            action=action,
            price=price_val,
            threshold=threshold,
            detail=detail,
        )
    )
    await session.commit()


async def _tick() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User)
            .join(Subscription, Subscription.user_id == User.id)
            .join(TeslaAccount, TeslaAccount.user_id == User.id)
            .where(
                User.auto_charge_enabled.is_(True),
                Subscription.active.is_(True),
            )
            .options(selectinload(User.tesla), selectinload(User.subscription))
        )
        users = result.scalars().unique().all()
        for user in users:
            try:
                await _evaluate_user(session, user)
            except Exception as e:
                log.exception("evaluate_user failed: %s", e)


async def run_forever() -> None:
    interval = max(60, int(get_settings().scheduler_interval_seconds))
    log.info("scheduler running every %ss", interval)
    while True:
        started = datetime.now(timezone.utc)
        try:
            await _tick()
        except Exception:
            log.exception("scheduler tick failed")
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        await asyncio.sleep(max(1, interval - int(elapsed)))
