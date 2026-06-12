import asyncio
from app.db import SessionLocal
from app.models import User
from app import tesla
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from jose import jwt

async def main():
    async with SessionLocal() as db:
        user = (await db.execute(select(User).options(selectinload(User.tesla)).where(User.id == 1))).scalar_one()
        token = await tesla.get_access_token(db, user)
        decoded = jwt.decode(token, "", options={"verify_signature": False, "verify_aud": False})
        print("Token payload:", decoded)

asyncio.run(main())