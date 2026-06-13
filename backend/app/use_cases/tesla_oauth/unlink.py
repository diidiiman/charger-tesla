from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User


class UnlinkTeslaOAuthUseCase:
    async def call(self, db: AsyncSession, user: User) -> dict:
        if user.tesla is not None:
            await db.delete(user.tesla)
            await db.commit()
        return {"ok": True}
