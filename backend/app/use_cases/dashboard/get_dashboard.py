import asyncio
import math
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, VehicleState
from app.schemas import DashboardResponse, CurrentPrice
from app import tesla, prices
from .get_settings import GetSettingsUseCase


class GetDashboardUseCase:
    async def call(self, db: AsyncSession, user: User) -> DashboardResponse:
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

                # Fetch state from DB instead of Tesla API
                state = (
                    await db.execute(
                        select(VehicleState).where(
                            VehicleState.vehicle_id == user.tesla.vehicle_id
                        )
                    )
                ).scalar_one_or_none()
                if state:
                    charge = {
                        "charging_state": state.charging_state or "Unknown",
                        "battery_level": state.battery_level,
                        "battery_range": (
                            float(state.battery_range)
                            if state.battery_range is not None
                            else None
                        ),
                        "charger_power": (
                            float(state.charger_power)
                            if state.charger_power is not None
                            else None
                        ),
                        "minutes_to_full_charge": state.minutes_to_full_charge,
                        "charge_limit_soc": state.charge_limit_soc,
                    }
                    if state.latitude is not None and state.longitude is not None:
                        vehicle["location"] = {
                            "latitude": float(state.latitude),
                            "longitude": float(state.longitude),
                        }
                else:
                    charge = {"charging_state": "Unknown", "battery_level": None}

                vehicle["is_at_home"] = False
                if (
                    "location" in vehicle
                    and user.home_latitude is not None
                    and user.home_longitude is not None
                ):
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
                p_data = await prices.current_price(user.region)
                if user.vat_included:
                    p_data["price"] *= prices.get_vat_multiplier(user.region)
                price = CurrentPrice(**p_data)
            except Exception:
                price = None

        sub = user.subscription
        return DashboardResponse(
            settings=await GetSettingsUseCase().call(user),
            tesla_linked=tesla_linked,
            vehicle=vehicle,
            price=price,
            charge=charge,
            subscription_active=bool(sub and sub.active),
        )
