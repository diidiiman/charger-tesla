from app.models import User
from app.schemas import SubscriptionStatus


class GetSubscriptionStatusUseCase:
    async def call(self, user: User) -> SubscriptionStatus:
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
