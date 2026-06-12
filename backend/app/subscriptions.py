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
    # TODO: load the service-account JSON, request an OAuth token for
    # https://www.googleapis.com/auth/androidpublisher, then call:
    #   GET https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/purchases/subscriptionsv2/tokens/{purchaseToken}
    # Use `lineItems[*].expiryTime` to set `expires_at`.
    _ = settings.play_package_name
    return _stub_response(receipt, product_id="charging_pro_monthly")


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
