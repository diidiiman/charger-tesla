from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2 import id_token
from google.auth.transport import requests
from app.models import User
from app.schemas import SessionToken
from app.security import make_session_token


class AuthGoogleUseCase:
    async def call(
        self, db: AsyncSession, id_token_str: str, device_id: str | None
    ) -> SessionToken:
        try:
            idinfo = id_token.verify_oauth2_token(id_token_str, requests.Request())
            google_id = idinfo["sub"]
            email = idinfo.get("email")
        except ValueError as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, f"Invalid Google token: {e}"
            )

        user = (
            await db.execute(select(User).where(User.google_id == google_id))
        ).scalar_one_or_none()

        if not user:
            if device_id:
                user = (
                    await db.execute(select(User).where(User.device_id == device_id))
                ).scalar_one_or_none()

            if user:
                user.google_id = google_id
                if email and not user.email:
                    user.email = email
            else:
                user = User(google_id=google_id, email=email, device_id=device_id)
                db.add(user)

            await db.commit()
            await db.refresh(user)

        return SessionToken(token=make_session_token(user.id), user_id=user.id)
