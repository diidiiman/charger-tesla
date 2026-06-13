from fastapi import HTTPException
from app.models import User
from app.schemas import CurrentPrice
from app import prices


class GetPriceUseCase:
    async def call(self, user: User) -> CurrentPrice:
        if not user.region:
            raise HTTPException(400, "no region selected")
        try:
            data = await prices.current_price(user.region)
            if user.vat_included:
                data["price"] *= prices.get_vat_multiplier(user.region)
        except Exception as e:
            raise HTTPException(502, f"price provider error: {e}") from e
        return CurrentPrice(**data)
