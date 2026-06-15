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

        was_active = False
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
            was_active = sub.active
            sub.platform = body.platform
            sub.product_id = body.product_id
            sub.receipt = body.receipt
            sub.active = result["active"]
            sub.expires_at = result["expires_at"]

        # If a subscription lapses, automatically disable auto-charging.
        # If it becomes active for the first time or is restored, enable auto-charging.
        if result["active"] and not was_active:
            user.auto_charge_enabled = True
        elif not result["active"]:
            user.auto_charge_enabled = False

        await db.commit()
        await db.refresh(sub)
        
        # Sync schedule (either to set it up for a new pro plan, or to clear it if lapsed)
        try:
            from app.scheduler import sync_charge_schedule
            await sync_charge_schedule(db, user)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to sync schedule in VerifySubscriptionUseCase: {e}")

        return SubscriptionStatus(
            active=sub.active,
            product_id=sub.product_id,
            expires_at=sub.expires_at,
            platform=sub.platform,
        )
