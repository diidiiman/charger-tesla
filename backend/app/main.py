import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes import auth, dashboard, subscription, tesla_oauth
from .scheduler import run_forever

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(run_forever(), name="auto-charge-scheduler")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(
    title="Tesla Charger",
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


@app.get("/health")
async def health() -> dict:
    return {"ok": True}

@app.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
async def get_public_key() -> PlainTextResponse:
    with open("com.tesla.3p.public-key.pem", "r") as f:
        return PlainTextResponse(f.read())
