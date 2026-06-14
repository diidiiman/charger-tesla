import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes import auth, dashboard, subscription, tesla_oauth, telemetry
from .scheduler import run_forever, fetch_daily_prices_forever
from .mqtt_subscriber import run_mqtt_subscriber

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(run_forever(), name="auto-charge-scheduler")
    price_task = asyncio.create_task(
        fetch_daily_prices_forever(), name="price-fetcher-scheduler"
    )
    mqtt_task = asyncio.create_task(run_mqtt_subscriber(), name="mqtt-subscriber")
    try:
        yield
    finally:
        task.cancel()
        price_task.cancel()
        mqtt_task.cancel()
        try:
            await asyncio.gather(task, price_task, mqtt_task, return_exceptions=True)
        except Exception:
            pass


app = FastAPI(
    title="Tesla Nord Pool",
    version="0.1.0",
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


@app.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
async def get_public_key() -> PlainTextResponse:
    with open("com.tesla.3p.public-key.pem", "r") as f:
        return PlainTextResponse(f.read())
