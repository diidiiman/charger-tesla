from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import SubscriptionStatus, SubscriptionSubmit
from ..security import current_user

from ..use_cases.subscription.get_status import GetSubscriptionStatusUseCase
from ..use_cases.subscription.verify import VerifySubscriptionUseCase
from ..use_cases.subscription.cancel import CancelSubscriptionUseCase

router = APIRouter(prefix="/v1/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionStatus)
async def get_status(user: User = Depends(current_user)) -> SubscriptionStatus:
    return await GetSubscriptionStatusUseCase().call(user)


@router.post("/verify", response_model=SubscriptionStatus)
async def verify(
    body: SubscriptionSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> SubscriptionStatus:
    return await VerifySubscriptionUseCase().call(db, user, body)


@router.delete("", response_model=dict)
async def cancel(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    return await CancelSubscriptionUseCase().call(db, user)
