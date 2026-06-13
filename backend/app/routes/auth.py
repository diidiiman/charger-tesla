from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import DeviceRegister, SessionToken, SocialAuth

from ..use_cases.auth.register_device import RegisterDeviceUseCase
from ..use_cases.auth.auth_google import AuthGoogleUseCase
from ..use_cases.auth.auth_apple import AuthAppleUseCase

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/device", response_model=SessionToken)
async def register_device(
    body: DeviceRegister, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    return await RegisterDeviceUseCase().call(db, body.device_id)


@router.post("/google", response_model=SessionToken)
async def auth_google(
    body: SocialAuth, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    return await AuthGoogleUseCase().call(db, body.id_token, body.device_id)


@router.post("/apple", response_model=SessionToken)
async def auth_apple(
    body: SocialAuth, db: AsyncSession = Depends(get_db)
) -> SessionToken:
    return await AuthAppleUseCase().call(db, body.id_token, body.device_id)
