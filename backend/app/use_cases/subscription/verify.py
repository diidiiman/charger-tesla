from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Subscription
from app.schemas import SubscriptionStatus, SubscriptionSubmit
from app import subscriptions


class VerifySubscriptionUseCase:
    async def call(
        self, db: AsyncSession, user: User, body: SubscriptionSubmit
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
