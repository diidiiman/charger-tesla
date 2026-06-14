"""In-app purchase subscription verification.

This module exposes one function — `verify_receipt(platform, receipt)` — that
returns `{active, expires_at, product_id, raw}`.

The full Apple App Store Server API + Google Play Developer API integrations
require platform credentials (App Store Connect P8 key + Play service-account
JSON) and are out of scope for this scaffold. The shape below is what the rest
of the codebase expects, with `TODO` markers showing exactly where to plug each
SDK call in. When STUB_ALLOW_ALL=True (default in dev) the verifier optimistically
trusts any non-empty receipt — flip it off before shipping to production.
"""

from datetime import datetime, timedelta, timezone
from .config import get_settings

STUB_ALLOW_ALL = True  # set False once real verification is wired in


async def verify_receipt(platform: str, receipt: str) -> dict:
    if not receipt:
        return {"active": False, "expires_at": None, "product_id": None, "raw": None}

    if platform == "ios":
        return await _verify_apple(receipt)
    if platform == "android":
        return await _verify_google(receipt)
    raise ValueError(f"unknown platform '{platform}'")


async def _verify_apple(receipt: str) -> dict:
    settings = get_settings()
    # TODO: build a JWT with the App Store Connect P8 key (KEY_ID, ISSUER_ID,
    # BUNDLE_ID) and call:
    #   POST https://api.storekit{-sandbox}.itunes.apple.com/inApps/v1/transactions/{transactionId}
    # to look up the latest transaction. Then read `expiresDate` to set `expires_at`.
    _ = settings.appstore_bundle_id, settings.appstore_use_sandbox
    return _stub_response(receipt, product_id="charging_pro_monthly")


async def _verify_google(receipt: str) -> dict:
    settings = get_settings()
    
    if not settings.play_service_account_json_path:
        raise ValueError("play_service_account_json_path is not configured")
        
    import json
    import httpx
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    
    # Load credentials and get token
    scopes = ["https://www.googleapis.com/auth/androidpublisher"]
    creds = service_account.Credentials.from_service_account_file(
        settings.play_service_account_json_path, scopes=scopes
    )
    creds.refresh(Request())
    
    product_id = "charging_pro_monthly"
    package_name = settings.play_package_name
    
    url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package_name}/purchases/subscriptionsv2/tokens/{receipt}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {creds.token}"}
        )
        
    if response.status_code != 200:
        # 404 typically means the purchase token is invalid
        return {
            "active": False,
            "expires_at": None,
            "product_id": product_id,
            "raw": {"status": response.status_code, "text": response.text}
        }
        
    data = response.json()
    
    # Check if subscription is active
    # A subscription is generally active if it has lineItems with an expiryTime in the future
    line_items = data.get("lineItems", [])
    if not line_items:
        return {
            "active": False,
            "expires_at": None,
            "product_id": product_id,
            "raw": data
        }
        
    # Find the furthest expiry time among the items
    expires_at_dt = None
    active = False
    
    for item in line_items:
        expiry_time_str = item.get("expiryTime")
        if expiry_time_str:
            # expiryTime is an ISO-8601 string, e.g., "2024-04-12T15:20:30.123Z"
            try:
                # Replace Z with +00:00 for fromisoformat compatibility in older Python versions, 
                # though Python 3.11+ handles Z.
                dt = datetime.fromisoformat(expiry_time_str.replace("Z", "+00:00"))
                if expires_at_dt is None or dt > expires_at_dt:
                    expires_at_dt = dt
            except ValueError:
                pass
                
    if expires_at_dt and expires_at_dt > datetime.now(timezone.utc):
        active = True
        
    return {
        "active": active,
        "expires_at": expires_at_dt,
        "product_id": product_id,
        "raw": data
    }


def _stub_response(receipt: str, product_id: str) -> dict:
    active = bool(STUB_ALLOW_ALL and receipt)
    return {
        "active": active,
        "expires_at": (
            (datetime.now(timezone.utc) + timedelta(days=31)) if active else None
        ),
        "product_id": product_id,
        "raw": {"stub": True, "received_len": len(receipt)},
    }
