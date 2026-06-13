from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User


class CancelSubscriptionUseCase:
    async def call(self, db: AsyncSession, user: User) -> dict:
        sub = user.subscription
        if sub:
            await db.delete(sub)
            user.auto_charge_enabled = False
            await db.commit()
        return {"ok": True}
