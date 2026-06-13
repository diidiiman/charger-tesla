from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.schemas import UserSettingsUpdate, UserSettings
from app import prices
from .get_settings import GetSettingsUseCase


class UpdateSettingsUseCase:
    async def call(
        self, db: AsyncSession, user: User, body: UserSettingsUpdate
    ) -> UserSettings:
        if body.region is not None:
            if body.region not in prices.VALID_REGION_CODES:
                raise HTTPException(400, f"unknown region '{body.region}'")
            user.region = body.region
        if body.threshold_price is not None:
            if body.threshold_price < 0:
                raise HTTPException(400, "threshold_price must be ≥ 0")
            user.threshold_price = body.threshold_price
        if body.vat_included is not None:
            user.vat_included = body.vat_included
        if body.units is not None:
            user.units = body.units
        if body.home_latitude is not None:
            user.home_latitude = body.home_latitude
        if body.home_longitude is not None:
            user.home_longitude = body.home_longitude
        if body.push_token is not None:
            user.push_token = body.push_token
        if body.price_change_reminder is not None:
            user.price_change_reminder = body.price_change_reminder
        if body.auto_charge_enabled is not None:
            sub = user.subscription
            if body.auto_charge_enabled and not (sub and sub.active):
                raise HTTPException(402, "auto_charge requires an active subscription")
            user.auto_charge_enabled = body.auto_charge_enabled
        await db.commit()
        await db.refresh(user)
        return await GetSettingsUseCase().call(user)
