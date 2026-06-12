from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import DeviceRegister, SessionToken
from ..security import make_session_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/device", response_model=SessionToken)
async def register_device(
    body: DeviceRegister, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    """Idempotent: same device_id always resolves to the same user row."""
    user = (
        await db.execute(select(User).where(User.device_id == body.device_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(device_id=body.device_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return SessionToken(token=make_session_token(user.id), user_id=user.id)
