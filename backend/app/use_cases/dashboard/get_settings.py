from app.models import User
from app.schemas import UserSettings


class GetSettingsUseCase:
    async def call(self, user: User) -> UserSettings:
        return UserSettings(
            region=user.region,
            threshold_price=(
                float(user.threshold_price)
                if user.threshold_price is not None
                else None
            ),
            currency=user.currency,
            vat_included=user.vat_included,
            units=user.units,
            home_latitude=user.home_latitude,
            home_longitude=user.home_longitude,
            push_token=user.push_token,
            price_change_reminder=user.price_change_reminder,
            auto_charge_enabled=user.auto_charge_enabled,
        )
