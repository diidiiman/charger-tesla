from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import subscriptions
from ..db import get_db
from ..models import Subscription, User
from ..schemas import SubscriptionStatus, SubscriptionSubmit
from ..security import current_user

router = APIRouter(prefix="/v1/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionStatus)
async def get_status(user: User = Depends(current_user)) -> SubscriptionStatus:
    sub = user.subscription
    if sub is None:
        return SubscriptionStatus(
            active=False, product_id=None, expires_at=None, platform=None
        )
    return SubscriptionStatus(
        active=sub.active,
        product_id=sub.product_id,
        expires_at=sub.expires_at,
        platform=sub.platform,
    )


@router.post("/verify", response_model=SubscriptionStatus)
async def verify(
    body: SubscriptionSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> SubscriptionStatus:
    if body.platform not in ("ios", "android"):
        raise HTTPException(400, "platform must be 'ios' or 'android'")

    result = await subscriptions.verify_receipt(body.platform, body.receipt)

    sub = user.subscription
    if sub is None:
        sub = Subscription(
            user_id=user.id,
            platform=body.platform,
            product_id=body.product_id,
            receipt=body.receipt,
            active=result["active"],
            expires_at=result["expires_at"],
        )
        db.add(sub)
    else:
        sub.platform = body.platform
        sub.product_id = body.product_id
        sub.receipt = body.receipt
        sub.active = result["active"]
        sub.expires_at = result["expires_at"]

    # If a subscription lapses, automatically disable auto-charging.
    if not result["active"]:
        user.auto_charge_enabled = False

    await db.commit()
    await db.refresh(sub)

    return SubscriptionStatus(
        active=sub.active,
        product_id=sub.product_id,
        expires_at=sub.expires_at,
        platform=sub.platform,
    )

@router.delete("", response_model=dict)
async def cancel(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    sub = user.subscription
    if sub:
        await db.delete(sub)
        user.auto_charge_enabled = False
        await db.commit()
    return {"ok": True}
