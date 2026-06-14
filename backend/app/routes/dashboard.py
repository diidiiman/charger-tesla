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
        home_latitude=user.home_latitude,
        home_longitude=user.home_longitude,
        push_token=user.push_token,
        price_change_reminder=user.price_change_reminder,
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
    if body.home_latitude is not None:
        user.home_latitude = body.home_latitude
    if body.home_longitude is not None:
        user.home_longitude = body.home_longitude
    if body.push_token is not None:
        user.push_token = body.push_token
    if body.price_change_reminder is not None:
        user.price_change_reminder = body.price_change_reminder
    if body.auto_charge_enabled is not None:
        sub = user.subscription
        if body.auto_charge_enabled and not (sub and sub.active):
            raise HTTPException(402, "auto_charge requires an active subscription")
        user.auto_charge_enabled = body.auto_charge_enabled
    await db.commit()
    await db.refresh(user)
    return _user_settings(user)


@router.get("/price", response_model=CurrentPrice)
async def get_price(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user)
) -> CurrentPrice:
    if not user.region:
        raise HTTPException(400, "no region selected")
    try:
        data = await prices.current_price(db, user.region)
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

                async def fetch_data():
                    from ..models import VehicleState
                    from sqlalchemy import select
                    
                    # 1. Try fetching from cached telemetry (VehicleState) first
                    state_db = (
                        await db.execute(
                            select(VehicleState).where(VehicleState.vehicle_id == user.tesla.vehicle_vin)
                        )
                    ).scalar_one_or_none()
                    
                    # Determine if cached data is fresh (updated within the last 15 minutes)
                    state_is_fresh = False
                    if state_db and state_db.updated_at:
                        time_diff = datetime.now(timezone.utc) - state_db.updated_at.replace(tzinfo=timezone.utc)
                        if time_diff.total_seconds() < 900:
                            state_is_fresh = True
                            
                    if state_is_fresh:
                        return {
                            "response": {
                                "charge_state": {
                                    "charging_state": state_db.charging_state,
                                    "battery_level": state_db.battery_level,
                                    "battery_range": float(state_db.battery_range) if state_db.battery_range else None,
                                    "charger_power": float(state_db.charger_power) if state_db.charger_power else None,
                                    "minutes_to_full_charge": state_db.minutes_to_full_charge,
                                    "charge_limit_soc": state_db.charge_limit_soc,
                                },
                                "drive_state": {
                                    "latitude": float(state_db.latitude) if state_db.latitude else None,
                                    "longitude": float(state_db.longitude) if state_db.longitude else None,
                                }
                            }
                        }

                    # 2. Fallback to API polling for pre-2021 vehicles or if telemetry is stale
                    try:
                        return await tesla.vehicle_data(token, user.tesla.vehicle_id)
                    except ValueError:
                        # Asleep or offline. Try to wake.
                        await tesla.wake_up(token, user.tesla.vehicle_id)
                        for _ in range(6):
                            await asyncio.sleep(5)
                            try:
                                return await tesla.vehicle_data(
                                    token, user.tesla.vehicle_id
                                )
                            except ValueError:
                                pass
                        raise ValueError("Vehicle is asleep or offline")

                data = await fetch_data()
                resp = data.get("response") or {}
                charge = resp.get("charge_state") or resp or data
                location = resp.get("drive_state")
                if location and "latitude" in location and "longitude" in location:
                    vehicle["location"] = {
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                    }
            except ValueError:
                charge = {"charging_state": "Asleep", "battery_level": None}
            except Exception as e:
                charge = {"error": str(e)[:200], "charging_state": "Unknown"}

            vehicle["is_at_home"] = False
            if (
                "location" in vehicle
                and user.home_latitude is not None
                and user.home_longitude is not None
            ):
                import math

                lat_diff = (
                    vehicle["location"]["latitude"] - float(user.home_latitude)
                ) * 111000
                lon_diff = (
                    (vehicle["location"]["longitude"] - float(user.home_longitude))
                    * 111000
                    * math.cos(math.radians(float(user.home_latitude)))
                )
                distance_meters = math.sqrt(lat_diff**2 + lon_diff**2)
                vehicle["is_at_home"] = distance_meters <= 200

    price = None
    if user.region:
        try:
            p_data = await prices.current_price(db, user.region)
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

    async def execute_start():
        try:
            return await tesla.charge_start(token, user.tesla.vehicle_id)
        except ValueError:
            await tesla.wake_up(token, user.tesla.vehicle_id)
            for _ in range(6):
                await asyncio.sleep(5)
                try:
                    return await tesla.charge_start(token, user.tesla.vehicle_id)
                except ValueError:
                    pass
            raise ValueError("Vehicle is asleep or offline")

    res = await execute_start()

    # Poll for up to 30 seconds to wait for state transition
    for _ in range(6):
        await asyncio.sleep(5)
        try:
            state_data = await tesla.vehicle_data(token, user.tesla.vehicle_id)
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

    async def execute_stop():
        try:
            return await tesla.charge_stop(token, user.tesla.vehicle_id)
        except ValueError:
            await tesla.wake_up(token, user.tesla.vehicle_id)
            for _ in range(6):
                await asyncio.sleep(5)
                try:
                    return await tesla.charge_stop(token, user.tesla.vehicle_id)
                except ValueError:
                    pass
            raise ValueError("Vehicle is asleep or offline")

    res = await execute_stop()

    # Poll for up to 30 seconds to wait for state transition
    for _ in range(6):
        await asyncio.sleep(5)
        try:
            state_data = await tesla.vehicle_data(token, user.tesla.vehicle_id)
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
    res = await tesla.wake_up(token, user.tesla.vehicle_id)

    # Poll for up to 30 seconds to wait for the vehicle to wake up
    for _ in range(6):
        await asyncio.sleep(5)
        try:
            state_data = await tesla.vehicle_data(token, user.tesla.vehicle_id)
            resp = state_data.get("response") or {}
            charge = resp.get("charge_state") or resp or state_data
            if charge.get("charging_state") not in ("Unknown", "Asleep", None):
                break
        except Exception:
            pass

    return res
