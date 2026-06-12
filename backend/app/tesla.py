"""Tesla Fleet API client + OAuth helpers."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .crypto import decrypt, encrypt
from .models import TeslaAccount, User

SCOPES = "openid offline_access vehicle_device_data vehicle_charging_cmds vehicle_cmds"


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def make_pkce() -> tuple[str, str, str]:
    code_verifier = _b64url(secrets.token_bytes(64))[:86]
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(secrets.token_bytes(16))
    return code_verifier, code_challenge, state


def build_authorize_url(code_challenge: str, state: str) -> str:
    s = get_settings()
    if not s.tesla_client_id or not s.tesla_redirect_uri:
        raise RuntimeError("Tesla client_id / redirect_uri not configured in .env")
    params = {
        "client_id": s.tesla_client_id,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": s.tesla_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "prompt": "login",
    }
    return f"{s.tesla_auth_base}/oauth2/v3/authorize?{urlencode(params)}"


def parse_callback_url(url: str) -> tuple[str | None, str | None]:
    q = parse_qs(urlparse(url).query)
    return (q.get("code", [None])[0], q.get("state", [None])[0])


async def _token_request(form: dict) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{s.tesla_auth_base}/oauth2/v3/token",
            data=form,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Tesla auth {r.status_code}: {r.text}")
    return r.json()


async def exchange_code(code: str, code_verifier: str) -> dict:
    s = get_settings()
    return await _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": s.tesla_client_id,
            "client_secret": s.tesla_client_secret,
            "code": code,
            "code_verifier": code_verifier,
            "audience": s.tesla_api_base,
            "redirect_uri": s.tesla_redirect_uri,
        }
    )


async def refresh_tokens(refresh_token: str) -> dict:
    s = get_settings()
    return await _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": s.tesla_client_id,
            "client_secret": s.tesla_client_secret,
            "refresh_token": refresh_token,
            "scope": SCOPES,
        }
    )


def store_tokens(account: TeslaAccount, tokens: dict) -> None:
    account.access_token_enc = encrypt(tokens["access_token"])
    account.refresh_token_enc = encrypt(tokens["refresh_token"])
    # 30s safety buffer.
    account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=max(60, int(tokens.get("expires_in", 28_800)) - 30)
    )


async def get_access_token(db: AsyncSession, user: User) -> str:
    account = user.tesla
    if account is None:
        raise RuntimeError("Tesla account not linked")
    if datetime.now(timezone.utc) < account.access_token_expires_at:
        return decrypt(account.access_token_enc)

    refreshed = await refresh_tokens(decrypt(account.refresh_token_enc))
    store_tokens(account, refreshed)
    await db.commit()
    return decrypt(account.access_token_enc)


async def _api(
    method: str, access_token: str, path: str, json: dict | None = None
) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request(
            method,
            f"{s.tesla_api_base}{path}",
            headers={"authorization": f"Bearer {access_token}"},
            json=json,
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Tesla API {r.status_code} on {path}: {r.text}")
    return r.json() if r.content else {}


async def list_vehicles(access_token: str) -> list[dict]:
    data = await _api("GET", access_token, "/api/1/vehicles")
    return data.get("response", []) or []


async def wake_up(access_token: str, vehicle_id: str) -> dict:
    return await _api("POST", access_token, f"/api/1/vehicles/{vehicle_id}/wake_up")


async def charge_state(access_token: str, vehicle_id: str) -> dict:
    return await _api(
        "GET", access_token, f"/api/1/vehicles/{vehicle_id}/data_request/charge_state"
    )


async def charge_start(access_token: str, vehicle_id: str) -> dict:
    return await _api(
        "POST", access_token, f"/api/1/vehicles/{vehicle_id}/command/charge_start"
    )


async def charge_stop(access_token: str, vehicle_id: str) -> dict:
    return await _api(
        "POST", access_token, f"/api/1/vehicles/{vehicle_id}/command/charge_stop"
    )
