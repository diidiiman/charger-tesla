from datetime import datetime, timedelta, timezone
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .config import get_settings
from .db import get_db
from .models import User

ALGO = "HS256"


def make_session_token(user_id: int) -> str:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.session_jwt_ttl_hours)
    payload = {"sub": str(user_id), "exp": exp}
    return jwt.encode(payload, settings.session_jwt_secret, algorithm=ALGO)


def decode_session_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token, get_settings().session_jwt_secret, algorithms=[ALGO]
        )
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session") from exc


async def current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    user_id = decode_session_token(authorization.split(None, 1)[1].strip())
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
