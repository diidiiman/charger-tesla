import asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app import tesla


class ChargeWakeUseCase:
    async def call(self, db: AsyncSession, user: User) -> dict:
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
