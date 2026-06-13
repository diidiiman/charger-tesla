import asyncio
from app.db import SessionLocal
from app.models import User
from app import tesla
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import httpx

async def main():
    async with SessionLocal() as db:
        user = (await db.execute(select(User).options(selectinload(User.tesla)).where(User.id == 1))).scalar_one()
        if not user.tesla:
            print("No Tesla account linked to User 1")
            return
            
        token = await tesla.get_access_token(db, user)
        s = tesla.get_settings()
        
        async with httpx.AsyncClient() as client:
            print("\n--- Requesting /api/1/vehicles ---")
            r1 = await client.request(
                "GET",
                f"{s.tesla_api_base}/api/1/vehicles",
                headers={"authorization": f"Bearer {token}"},
            )
            print("Status:", r1.status_code)
            print("Body:", r1.text)

asyncio.run(main())