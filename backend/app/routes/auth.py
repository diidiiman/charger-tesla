from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2 import id_token
from google.auth.transport import requests
from jose import jwt

from ..db import get_db
from ..models import User
from ..schemas import DeviceRegister, SessionToken, SocialAuth
from ..security import make_session_token
from ..config import get_settings

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


@router.post("/google", response_model=SessionToken)
async def auth_google(
    body: SocialAuth, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    try:
        # We don't enforce an audience strictly here to allow both iOS and Android client IDs
        idinfo = id_token.verify_oauth2_token(body.id_token, requests.Request())
        google_id = idinfo["sub"]
        email = idinfo.get("email")
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Google token: {e}")

    user = (await db.execute(select(User).where(User.google_id == google_id))).scalar_one_or_none()
    
    if not user:
        if body.device_id:
            user = (await db.execute(select(User).where(User.device_id == body.device_id))).scalar_one_or_none()
        
        if user:
            user.google_id = google_id
            if email and not user.email:
                user.email = email
        else:
            user = User(google_id=google_id, email=email, device_id=body.device_id)
            db.add(user)
        
        await db.commit()
        await db.refresh(user)

    return SessionToken(token=make_session_token(user.id), user_id=user.id)


@router.post("/apple", response_model=SessionToken)
async def auth_apple(
    body: SocialAuth, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    try:
        # Decode without verifying signature for MVP purposes
        decoded = jwt.decode(body.id_token, "", options={"verify_signature": False, "verify_aud": False})
        if decoded.get("iss") != "https://appleid.apple.com":
            raise ValueError("Invalid issuer")
        apple_id = decoded["sub"]
        email = decoded.get("email")
    except Exception as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Apple token: {e}")

    user = (await db.execute(select(User).where(User.apple_id == apple_id))).scalar_one_or_none()
    
    if not user:
        if body.device_id:
            user = (await db.execute(select(User).where(User.device_id == body.device_id))).scalar_one_or_none()
            
        if user:
            user.apple_id = apple_id
            if email and not user.email:
                user.email = email
        else:
            user = User(apple_id=apple_id, email=email, device_id=body.device_id)
            db.add(user)
            
        await db.commit()
        await db.refresh(user)

    return SessionToken(token=make_session_token(user.id), user_id=user.id)
