from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VehicleState, User, TeslaAccount
from app.schemas import TelemetryWebhookPayload
import asyncio


class ProcessTelemetryWebhookUseCase:
    async def call(self, db: AsyncSession, payload: TelemetryWebhookPayload) -> dict:
        state = (
            await db.execute(
                select(VehicleState).where(
                    VehicleState.vehicle_id == payload.vehicle_id
                )
            )
        ).scalar_one_or_none()

        if not state:
            state = VehicleState(vehicle_id=payload.vehicle_id)
            db.add(state)

        if payload.charging_state is not None:
            state.charging_state = payload.charging_state
        if payload.battery_level is not None:
            state.battery_level = payload.battery_level
        if payload.battery_range is not None:
            state.battery_range = payload.battery_range
        if payload.charger_power is not None:
            state.charger_power = payload.charger_power
        if payload.minutes_to_full_charge is not None:
            state.minutes_to_full_charge = payload.minutes_to_full_charge
        if payload.charge_limit_soc is not None:
            state.charge_limit_soc = payload.charge_limit_soc
        if payload.latitude is not None:
            state.latitude = payload.latitude
        if payload.longitude is not None:
            state.longitude = payload.longitude

        await db.commit()
        
        return {"ok": True}
