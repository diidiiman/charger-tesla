from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import RedirectResponse
from fastapi import Request
from app.models import OAuthState, User, TeslaAccount
from app.config import get_settings
from app import tesla


class CallbackTeslaOAuthUseCase:
    async def call(self, request: Request, db: AsyncSession) -> RedirectResponse:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        settings = get_settings()

        if not code or not state:
            # Fallback if state is missing
            return_url = f"{settings.mobile_deep_link_scheme}://auth"
            return RedirectResponse(
                f"{return_url}?ok=0&error=missing_code", status_code=302
            )

        return_url = f"{settings.mobile_deep_link_scheme}://auth"
        if "|" in state:
            _, return_url = state.split("|", 1)

        row = (
            await db.execute(select(OAuthState).where(OAuthState.state == state))
        ).scalar_one_or_none()
        if row is None:
            return RedirectResponse(
                f"{return_url}?ok=0&error=unknown_state", status_code=302
            )

        code_verifier = row.code_verifier
        user_id = row.user_id
        await db.execute(delete(OAuthState).where(OAuthState.id == row.id))

        try:
            tokens = await tesla.exchange_code(code, code_verifier)
        except RuntimeError as e:
            await db.commit()
            return RedirectResponse(
                f"{return_url}?ok=0&error=exchange_failed&detail={str(e)[:64]}",
                status_code=302,
            )

        user = (
            await db.execute(
                select(User).options(selectinload(User.tesla)).where(User.id == user_id)
            )
        ).scalar_one()
        account = user.tesla or TeslaAccount(
            user_id=user.id,
            access_token_enc="",
            refresh_token_enc="",
            access_token_expires_at=datetime.now(timezone.utc),
        )
        if user.tesla is None:
            db.add(account)
        tesla.store_tokens(account, tokens)

        # Best-effort: fetch the first vehicle and cache its identity.
        try:
            vehicles = await tesla.list_vehicles(tokens["access_token"])
            if vehicles:
                v = vehicles[0]
                account.vehicle_id = str(v.get("id_s") or v.get("id") or "")
                account.vehicle_vin = v.get("vin")
                account.vehicle_display_name = v.get("display_name")
                
                # Configure the vehicle to start streaming telemetry
                if account.vehicle_vin:
                    await tesla.configure_telemetry(tokens["access_token"], account.vehicle_vin)
        except Exception as e:
            print(f"Failed to fetch vehicle or configure telemetry: {e}")

        await db.commit()
        return RedirectResponse(f"{return_url}?ok=1", status_code=302)
