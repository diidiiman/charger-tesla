from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import VehicleState, User, TeslaAccount
from app.schemas import TelemetryWebhookPayload
from app.scheduler import _evaluate_user
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

        should_evaluate = False

        if payload.charging_state is not None:
            if state.charging_state != payload.charging_state:
                # Trigger evaluation if the vehicle was plugged in or charging state changed
                should_evaluate = True
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
            if state.latitude != payload.latitude:
                should_evaluate = True
            state.latitude = payload.latitude
        if payload.longitude is not None:
            state.longitude = payload.longitude

        await db.commit()
        
        if should_evaluate:
            # Look up the user to run evaluation
            user = (
                await db.execute(
                    select(User)
                    .join(TeslaAccount, TeslaAccount.user_id == User.id)
                    .where(TeslaAccount.vehicle_vin == payload.vehicle_id)
                    .options(selectinload(User.tesla), selectinload(User.subscription))
                )
            ).scalar_one_or_none()
            
            if user:
                asyncio.create_task(_evaluate_user(db, user))

        return {"ok": True}
