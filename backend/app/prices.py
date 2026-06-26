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
from sqlalchemy import select

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
    {"code": "PL", "label": "Poland"},
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
    "PL": 1.23,
}


def get_vat_multiplier(region: str) -> float:
    country = region[:2]
    return VAT_RATES.get(country, 1.0)


async def current_price(db: AsyncSession, region: str, dt: datetime = None) -> dict:
    if region not in VALID_REGION_CODES:
        raise ValueError(f"unknown region '{region}'")
    
    if dt is None:
        dt = datetime.now(timezone.utc)
        
    stmt = select(RegionPrice).where(
        RegionPrice.region == region,
        RegionPrice.valid_from <= dt,
        RegionPrice.valid_to > dt
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    
    if record:
        return {
            "region": region,
            "currency": get_settings().price_currency,
            "unit": "EUR/kWh",
            "price": float(record.price),
            "valid_from": record.valid_from.isoformat(),
            "valid_to": record.valid_to.isoformat(),
            "provider": "nordpool",
        }
        
    # Not found in DB, fetch from API for this region and date
    await fetch_and_store_prices(db, dt, regions=[region])
    
    # Try fetching again
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    
    if record:
        return {
            "region": region,
            "currency": get_settings().price_currency,
            "unit": "EUR/kWh",
            "price": float(record.price),
            "valid_from": record.valid_from.isoformat(),
            "valid_to": record.valid_to.isoformat(),
            "provider": "nordpool",
        }
        
    raise RuntimeError(f"no current Nord Pool price for region {region}")


async def fetch_and_store_prices(db: AsyncSession, target_date: datetime, regions: list[str] = None):
    """Fetches day-ahead prices for regions for the target date and stores them in the database."""
    settings = get_settings()
    date_str = target_date.strftime("%Y-%m-%d")
    url = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"

    regions_to_fetch = regions if regions else VALID_REGION_CODES

    async with httpx.AsyncClient(timeout=30.0) as client:
        for region in regions_to_fetch:
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

                # Group entries by hour
                hourly_data = {}
                
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
                        # Group by the start hour
                        hour_key = start.replace(minute=0, second=0, microsecond=0)
                        if hour_key not in hourly_data:
                            hourly_data[hour_key] = {"sum": 0.0, "count": 0, "end": end}
                        
                        hourly_data[hour_key]["sum"] += float(price)
                        hourly_data[hour_key]["count"] += 1
                        
                        # Keep track of the latest end time for this hour block
                        if end > hourly_data[hour_key]["end"]:
                            hourly_data[hour_key]["end"] = end

                records = []
                for hour_start, data in hourly_data.items():
                    avg_price = data["sum"] / data["count"]
                    price_per_kwh = avg_price / 1000.0
                    price_with_vat = price_per_kwh * get_vat_multiplier(region)
                    
                    # Ensure the block represents exactly 1 hour for DB consistency
                    hour_end = hour_start + timedelta(hours=1)
                    
                    records.append(
                        {
                            "region": region,
                            "price": price_per_kwh,
                            "price_with_vat": price_with_vat,
                            "valid_from": hour_start,
                            "valid_to": hour_end,
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
                await db.rollback()
                print(f"Error fetching/storing prices for {region}: {e}")

            # Small delay to be polite to the API
            await asyncio.sleep(0.5)
