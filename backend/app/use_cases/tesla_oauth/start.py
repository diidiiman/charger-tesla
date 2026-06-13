from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, OAuthState
from app.schemas import AuthStartResponse, AuthStartRequest
from app import tesla


class StartTeslaOAuthUseCase:
    async def call(
        self, db: AsyncSession, user: User, body: AuthStartRequest
    ) -> AuthStartResponse:
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
