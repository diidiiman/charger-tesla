import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import prices, tesla
from ..db import get_db
from ..models import User
from ..schemas import (
    CurrentPrice,
    DashboardResponse,
    RegionInfo,
    UserSettings,
    UserSettingsUpdate,
)
from ..security import current_user

router = APIRouter(prefix="/v1", tags=["dashboard"])


@router.get("/regions", response_model=list[RegionInfo])
async def regions() -> list[RegionInfo]:
    return [RegionInfo(**r) for r in prices.list_regions()]


def _user_settings(user: User) -> UserSettings:
    return UserSettings(
        region=user.region,
        threshold_price=(
            float(user.threshold_price) if user.threshold_price is not None else None
        ),
        currency=user.currency,
        vat_included=user.vat_included,
        units=user.units,
        auto_charge_enabled=user.auto_charge_enabled,
    )


@router.get("/settings", response_model=UserSettings)
async def get_settings_endpoint(user: User = Depends(current_user)) -> UserSettings:
    return _user_settings(user)


@router.put("/settings", response_model=UserSettings)
async def update_settings(
    body: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> UserSettings:
    if body.region is not None:
        if body.region not in prices.VALID_REGION_CODES:
            raise HTTPException(400, f"unknown region '{body.region}'")
        user.region = body.region
    if body.threshold_price is not None:
        if body.threshold_price < 0:
            raise HTTPException(400, "threshold_price must be ≥ 0")
        user.threshold_price = body.threshold_price
    if body.vat_included is not None:
        user.vat_included = body.vat_included
    if body.units is not None:
        user.units = body.units
    if body.auto_charge_enabled is not None:
        sub = user.subscription
        if body.auto_charge_enabled and not (sub and sub.active):
            raise HTTPException(402, "auto_charge requires an active subscription")
        user.auto_charge_enabled = body.auto_charge_enabled
    await db.commit()
    await db.refresh(user)
    return _user_settings(user)


@router.get("/price", response_model=CurrentPrice)
async def get_price(user: User = Depends(current_user)) -> CurrentPrice:
    if not user.region:
        raise HTTPException(400, "no region selected")
    try:
        data = await prices.current_price(user.region)
        if user.vat_included:
            data["price"] *= prices.get_vat_multiplier(user.region)
    except Exception as e:
        raise HTTPException(502, f"price provider error: {e}") from e
    return CurrentPrice(**data)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> DashboardResponse:
    tesla_linked = user.tesla is not None
    vehicle = None
    charge = None
    if tesla_linked:
        if not user.tesla.vehicle_id:
            try:
                token = await tesla.get_access_token(db, user)
                vehicles = await tesla.list_vehicles(token)
                if vehicles:
                    v = vehicles[0]
                    user.tesla.vehicle_id = str(v.get("id_s") or v.get("id") or "")
                    user.tesla.vehicle_vin = v.get("vin")
                    user.tesla.vehicle_display_name = v.get("display_name")
                    await db.commit()
            except Exception as e:
                pass

        if user.tesla.vehicle_id:
            vehicle = {
                "id": user.tesla.vehicle_id,
                "vin": user.tesla.vehicle_vin,
                "display_name": user.tesla.vehicle_display_name,
            }
            try:
                token = await tesla.get_access_token(db, user)
                data = await tesla.charge_state(token, user.tesla.vehicle_id)
                # The new vehicle_data endpoint returns the state inside 'response.charge_state'
                resp = data.get("response") or {}
                charge = resp.get("charge_state") or resp or data
            except ValueError:
                charge = {"charging_state": "Asleep", "battery_level": None}
            except Exception as e:
                charge = {"error": str(e)[:200], "charging_state": "Unknown"}

    price = None
    if user.region:
        try:
            p_data = await prices.current_price(user.region)
            if user.vat_included:
                p_data["price"] *= prices.get_vat_multiplier(user.region)
            price = CurrentPrice(**p_data)
        except Exception:
            price = None

    sub = user.subscription
    return DashboardResponse(
        settings=_user_settings(user),
        tesla_linked=tesla_linked,
        vehicle=vehicle,
        price=price,
        charge=charge,
        subscription_active=bool(sub and sub.active),
    )


@router.post("/charge/start")
async def charge_start(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if user.tesla is None or not user.tesla.vehicle_id:
        raise HTTPException(400, "no Tesla vehicle linked")
    token = await tesla.get_access_token(db, user)
    res = await tesla.charge_start(token, user.tesla.vehicle_id)
    
    # Poll for up to 30 seconds to wait for state transition
    for _ in range(6):
        await asyncio.sleep(5)
        try:
            state_data = await tesla.charge_state(token, user.tesla.vehicle_id)
            resp = state_data.get("response") or {}
            charge = resp.get("charge_state") or resp or state_data
            if charge.get("charging_state") in ("Charging", "Starting", "Preparing"):
                break
        except Exception:
            pass
            
    return res


@router.post("/charge/stop")
async def charge_stop(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if user.tesla is None or not user.tesla.vehicle_id:
        raise HTTPException(400, "no Tesla vehicle linked")
    token = await tesla.get_access_token(db, user)
    res = await tesla.charge_stop(token, user.tesla.vehicle_id)
    
    # Poll for up to 30 seconds to wait for state transition
    for _ in range(6):
        await asyncio.sleep(5)
        try:
            state_data = await tesla.charge_state(token, user.tesla.vehicle_id)
            resp = state_data.get("response") or {}
            charge = resp.get("charge_state") or resp or state_data
            if charge.get("charging_state") == "Stopped":
                break
        except Exception:
            pass
            
    return res


@router.post("/charge/wake")
async def charge_wake(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if user.tesla is None or not user.tesla.vehicle_id:
        raise HTTPException(400, "no Tesla vehicle linked")
    token = await tesla.get_access_token(db, user)
    return await tesla.wake_up(token, user.tesla.vehicle_id)
