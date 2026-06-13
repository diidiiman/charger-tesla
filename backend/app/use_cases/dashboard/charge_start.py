import asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, VehicleState
from app import tesla


class ChargeStartUseCase:
    async def call(self, db: AsyncSession, user: User) -> dict:
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

        # Poll our local VehicleState database for up to 30 seconds
        for _ in range(6):
            await asyncio.sleep(5)
            # Refresh session to see new DB commits from the telemetry webhook
            await db.commit()
            state = (
                await db.execute(
                    select(VehicleState).where(
                        VehicleState.vehicle_id == user.tesla.vehicle_id
                    )
                )
            ).scalar_one_or_none()
            if state and state.charging_state in (
                "Charging",
                "Starting",
                "Preparing",
            ):
                break

        return res
