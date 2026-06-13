import asyncio
import httpx
from app.db import SessionLocal
from app.models import User
from app import tesla
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def main():
    async with SessionLocal() as db:
        user = (await db.execute(select(User).options(selectinload(User.tesla)).where(User.id == 1))).scalar_one()
        token = await tesla.get_access_token(db, user)
        s = tesla.get_settings()
        
        async with httpx.AsyncClient() as client:
            r = await client.request(
                "GET",
                f"{s.tesla_api_base}/api/1/vehicles/{user.tesla.vehicle_id}/vehicle_data?endpoints=charge_state%3Blocation_data",
                headers={"authorization": f"Bearer {token}"},
            )
            print("Status:", r.status_code)
            print("Body:", r.text)

if __name__ == "__main__":
    asyncio.run(main())