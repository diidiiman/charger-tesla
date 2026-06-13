from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
from app.models import User
from app.schemas import SessionToken
from app.security import make_session_token


class AuthAppleUseCase:
    async def call(
        self, db: AsyncSession, id_token_str: str, device_id: str | None
    ) -> SessionToken:
        try:
            # Decode without verifying signature for MVP purposes
            decoded = jwt.decode(
                id_token_str,
                "",
                options={"verify_signature": False, "verify_aud": False},
            )
            if decoded.get("iss") != "https://appleid.apple.com":
                raise ValueError("Invalid issuer")
            apple_id = decoded["sub"]
            email = decoded.get("email")
        except Exception as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, f"Invalid Apple token: {e}"
            )

        user = (
            await db.execute(select(User).where(User.apple_id == apple_id))
        ).scalar_one_or_none()

        if not user:
            if device_id:
                user = (
                    await db.execute(select(User).where(User.device_id == device_id))
                ).scalar_one_or_none()

            if user:
                user.apple_id = apple_id
                if email and not user.email:
                    user.email = email
            else:
                user = User(apple_id=apple_id, email=email, device_id=device_id)
                db.add(user)

            await db.commit()
            await db.refresh(user)

        return SessionToken(token=make_session_token(user.id), user_id=user.id)
