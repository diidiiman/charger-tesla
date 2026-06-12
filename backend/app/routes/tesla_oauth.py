from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .. import tesla
from ..config import get_settings
from ..db import get_db
from ..models import OAuthState, TeslaAccount, User
from ..schemas import AuthStartResponse, AuthStartRequest
from ..security import current_user

router = APIRouter(tags=["tesla-oauth"])


@router.post("/auth/tesla/start", response_model=AuthStartResponse)
async def start_oauth(
    body: AuthStartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> AuthStartResponse:
    """Issue a PKCE pair and bind it to this user. Mobile opens the returned URL."""
    code_verifier, code_challenge, base_state = tesla.make_pkce()
    
    state = base_state
    if body.return_url:
        state = f"{base_state}|{body.return_url}"

    # Discard any prior in-flight states for this user, plus stale globals.
    await db.execute(delete(OAuthState).where(OAuthState.user_id == user.id))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db.execute(delete(OAuthState).where(OAuthState.created_at < cutoff))

    db.add(OAuthState(state=state, code_verifier=code_verifier, user_id=user.id))
    await db.commit()

    return AuthStartResponse(
        authorize_url=tesla.build_authorize_url(code_challenge, state)
    )


@router.get("/callback")
async def callback(
    request: Request, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Tesla redirects the browser here after the user signs in.

    We exchange the code, persist the encrypted tokens, then deep-link the
    mobile app via the registered URL scheme (`teslacharger://...`).
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    settings = get_settings()
    scheme = settings.mobile_deep_link_scheme

    if not code or not state:
        # Fallback if state is missing
        return_url = f"{settings.mobile_deep_link_scheme}://auth"
        return RedirectResponse(f"{return_url}?ok=0&error=missing_code", status_code=302)

    return_url = f"{settings.mobile_deep_link_scheme}://auth"
    if "|" in state:
        _, return_url = state.split("|", 1)

    row = (
        await db.execute(select(OAuthState).where(OAuthState.state == state))
    ).scalar_one_or_none()
    if row is None:
        return RedirectResponse(f"{return_url}?ok=0&error=unknown_state", status_code=302)

    code_verifier = row.code_verifier
    user_id = row.user_id
    await db.execute(delete(OAuthState).where(OAuthState.id == row.id))

    try:
        tokens = await tesla.exchange_code(code, code_verifier)
    except RuntimeError as e:
        await db.commit()
        return RedirectResponse(
            f"{return_url}?ok=0&error=exchange_failed&detail={str(e)[:64]}", status_code=302
        )

    user = (await db.execute(select(User).options(selectinload(User.tesla)).where(User.id == user_id))).scalar_one()
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
    except Exception:
        pass

    await db.commit()
    return RedirectResponse(f"{return_url}?ok=1", status_code=302)


@router.post("/auth/tesla/unlink")
async def unlink(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if user.tesla is not None:
        await db.delete(user.tesla)
        await db.commit()
    return {"ok": True}
