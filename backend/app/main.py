import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .db import init_db, get_db
from .routes import auth, dashboard, subscription, tesla_oauth, telemetry
from .scheduler import fetch_daily_prices_forever, verify_expired_subscriptions_forever
from .mqtt_subscriber import run_mqtt_subscriber

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    price_task = asyncio.create_task(
        fetch_daily_prices_forever(), name="price-fetcher-scheduler"
    )
    sub_task = asyncio.create_task(
        verify_expired_subscriptions_forever(), name="subscription-verifier-scheduler"
    )
    mqtt_task = asyncio.create_task(run_mqtt_subscriber(), name="mqtt-subscriber")
    try:
        yield
    finally:
        price_task.cancel()
        sub_task.cancel()
        mqtt_task.cancel()
        try:
            await asyncio.gather(price_task, sub_task, mqtt_task, return_exceptions=True)
        except Exception:
            pass


app = FastAPI(
    title="Tesla Nord Pool",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Mobile clients live on a different origin (the deployed iOS/Android app),
# but the calls go to https://charging.clankersystems.com directly. CORS is open
# for the API surface — the JWT bearer token is the real auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tesla_oauth.router)
app.include_router(dashboard.router)
app.include_router(subscription.router)
app.include_router(telemetry.router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/rerun/schedule")
async def rerun_schedule(
    token: str = Header(..., alias="X-Auth-Token"),
    db: AsyncSession = Depends(get_db)
) -> dict:
    if token != "this-is-safe-to-run":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from datetime import datetime, timezone, timedelta
    from . import prices
    from .scheduler import _sync_all_users
    
    now = datetime.now(timezone.utc)
    target_date = now + timedelta(days=1)
    
    # 1. Fetch prices
    await prices.fetch_and_store_prices(db, target_date)
    # 2. Re-evaluate schedules for all active users
    await _sync_all_users(db, target_date.date())
    
    return {
        "ok": True, 
        "message": f"Successfully fetched prices and synced schedules for {target_date.date()}"
    }


@app.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
async def get_public_key() -> PlainTextResponse:
    with open("com.tesla.3p.public-key.pem", "r") as f:
        return PlainTextResponse(f.read())
