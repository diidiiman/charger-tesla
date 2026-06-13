from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import AuthStartResponse, AuthStartRequest
from ..security import current_user

from ..use_cases.tesla_oauth.start import StartTeslaOAuthUseCase
from ..use_cases.tesla_oauth.callback import CallbackTeslaOAuthUseCase
from ..use_cases.tesla_oauth.unlink import UnlinkTeslaOAuthUseCase

router = APIRouter(tags=["tesla-oauth"])


@router.post("/auth/tesla/start", response_model=AuthStartResponse)
async def start_oauth(
    body: AuthStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> AuthStartResponse:
    return await StartTeslaOAuthUseCase().call(db, user, body)


@router.get("/callback")
async def callback(
    request: Request, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    return await CallbackTeslaOAuthUseCase().call(request, db)


@router.post("/auth/tesla/unlink")
async def unlink(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return await UnlinkTeslaOAuthUseCase().call(db, user)
