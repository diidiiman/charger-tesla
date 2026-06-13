from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.schemas import SessionToken
from app.security import make_session_token


class RegisterDeviceUseCase:
    async def call(self, db: AsyncSession, device_id: str) -> SessionToken:
        user = (
            await db.execute(select(User).where(User.device_id == device_id))
        ).scalar_one_or_none()
        if user is None:
            user = User(device_id=device_id)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return SessionToken(token=make_session_token(user.id), user_id=user.id)
