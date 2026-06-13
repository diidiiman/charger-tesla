from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import TelemetryWebhookPayload
from ..use_cases.telemetry.process_webhook import ProcessTelemetryWebhookUseCase

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


@router.post("/webhook")
async def telemetry_webhook(
    payload: TelemetryWebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingests decoded JSON data forwarded from the Fleet Telemetry server."""
    return await ProcessTelemetryWebhookUseCase().call(db, payload)
