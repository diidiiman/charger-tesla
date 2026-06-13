"""Electricity day-ahead price provider.

Default implementation calls the Nord Pool day-ahead public dataportal-api
(https://dataportal-api.nordpoolgroup.com) — free, no auth, covers Nordic +
Baltic delivery areas. Swap by setting PRICE_PROVIDER in .env and adding a new
branch to `current_price()`.

Note: the original requirement mentioned a "Norstat" electricity price API.
That doesn't appear to be a real product; Nord Pool is the closest match and
covers the same Northern-European market. Replace this provider if you have
access to a different upstream.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from .config import get_settings
from .models import RegionPrice

# Nord Pool delivery areas exposed to the mobile app.
REGIONS: list[dict] = [
    {"code": "NO1", "label": "Norway — Oslo"},
    {"code": "NO2", "label": "Norway — Kristiansand"},
    {"code": "NO3", "label": "Norway — Trondheim"},
    {"code": "NO4", "label": "Norway — Tromsø"},
    {"code": "NO5", "label": "Norway — Bergen"},
    {"code": "SE1", "label": "Sweden — Luleå"},
    {"code": "SE2", "label": "Sweden — Sundsvall"},
    {"code": "SE3", "label": "Sweden — Stockholm"},
    {"code": "SE4", "label": "Sweden — Malmö"},
    {"code": "DK1", "label": "Denmark — West"},
    {"code": "DK2", "label": "Denmark — East"},
    {"code": "FI", "label": "Finland"},
    {"code": "EE", "label": "Estonia"},
    {"code": "LV", "label": "Latvia"},
    {"code": "LT", "label": "Lithuania"},
]
VALID_REGION_CODES = {r["code"] for r in REGIONS}


def list_regions() -> list[dict]:
    return REGIONS


async def _nordpool_current(region: str, dt: datetime = None) -> dict:
    settings = get_settings()
    if dt is None:
        dt = datetime.now(timezone.utc)
    today = dt.strftime("%Y-%m-%d")
    url = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
    params = {
        "date": today,
        "market": "DayAhead",
        "deliveryArea": region,
        "currency": settings.price_currency,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params, headers={"accept": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Nord Pool {r.status_code}: {r.text}")
    payload = r.json()

    # The dataportal response shape: multiAreaEntries: [{ deliveryStart, deliveryEnd, entryPerArea: { NO1: 12.34, ... } }]
    entries = payload.get("multiAreaEntries") or payload.get("entries") or []
    current = None
    for e in entries:
        start = datetime.fromisoformat(e["deliveryStart"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(e["deliveryEnd"].replace("Z", "+00:00"))
        if start <= dt < end:
            per_area = e.get("entryPerArea") or e.get("perArea") or {}
            price = per_area.get(region)
            if price is None and "value" in e:
                price = e["value"]
            current = {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "price": price,
            }
            break

    if current is None or current["price"] is None:
        raise RuntimeError(f"no current Nord Pool price for region {region}")

    # Nord Pool returns the area price per MWh; divide by 1000 to get per kWh.
    price_per_kwh = float(current["price"]) / 1000.0
    return {
        "region": region,
        "currency": settings.price_currency,
        "unit": "EUR/kWh",
        "price": price_per_kwh,
        "valid_from": current["start"],
        "valid_to": current["end"],
        "provider": "nordpool",
    }


VAT_RATES = {
    "NO": 1.25,
    "SE": 1.25,
    "DK": 1.25,
    "FI": 1.255,  # 25.5% since Sep 2024
    "EE": 1.22,
    "LV": 1.21,
    "LT": 1.21,
}


def get_vat_multiplier(region: str) -> float:
    country = region[:2]
    return VAT_RATES.get(country, 1.0)


async def current_price(region: str, dt: datetime = None) -> dict:
    if region not in VALID_REGION_CODES:
        raise ValueError(f"unknown region '{region}'")
    provider = get_settings().price_provider.lower()
    if provider == "nordpool":
        return await _nordpool_current(region, dt)
    raise RuntimeError(f"unknown PRICE_PROVIDER '{provider}'")


async def fetch_and_store_prices(db: AsyncSession, target_date: datetime):
    """Fetches day-ahead prices for all regions for the target date and stores them in the database."""
    settings = get_settings()
    date_str = target_date.strftime("%Y-%m-%d")
    url = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for region in VALID_REGION_CODES:
            params = {
                "date": date_str,
                "market": "DayAhead",
                "deliveryArea": region,
                "currency": settings.price_currency,
            }
            try:
                r = await client.get(
                    url, params=params, headers={"accept": "application/json"}
                )
                if r.status_code >= 400:
                    print(
                        f"Failed to fetch prices for {region} on {date_str}: {r.status_code}"
                    )
                    continue

                payload = r.json()
                entries = (
                    payload.get("multiAreaEntries") or payload.get("entries") or []
                )

                records = []
                for e in entries:
                    start = datetime.fromisoformat(
                        e["deliveryStart"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        e["deliveryEnd"].replace("Z", "+00:00")
                    )

                    per_area = e.get("entryPerArea") or e.get("perArea") or {}
                    price = per_area.get(region)
                    if price is None and "value" in e:
                        price = e["value"]

                    if price is not None:
                        price_per_kwh = float(price) / 1000.0
                        price_with_vat = price_per_kwh * get_vat_multiplier(region)
                        records.append(
                            {
                                "region": region,
                                "price": price_per_kwh,
                                "price_with_vat": price_with_vat,
                                "valid_from": start,
                                "valid_to": end,
                            }
                        )

                if records:
                    stmt = insert(RegionPrice).values(records)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["region", "valid_from"],
                        set_={
                            "price": stmt.excluded.price,
                            "price_with_vat": stmt.excluded.price_with_vat,
                            "valid_to": stmt.excluded.valid_to,
                        },
                    )
                    await db.execute(stmt)
                    await db.commit()

            except Exception as e:
                print(f"Error fetching/storing prices for {region}: {e}")

            # Small delay to be polite to the API
            await asyncio.sleep(0.5)
