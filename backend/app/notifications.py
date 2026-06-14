import httpx
import logging

log = logging.getLogger(__name__)


async def send_push_notification(
    push_token: str, title: str, body: str, data: dict = None
):
    if not push_token or not push_token.startswith("ExponentPushToken"):
        return

    payload = {
        "to": push_token,
        "title": title,
        "body": body,
        "data": data or {},
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post("https://exp.host/--/api/v2/push/send", json=payload)
            r.raise_for_status()
            response_data = r.json()
            
            # Expo returns 200 OK even if the individual token failed, so we must check the inner data
            data_payload = response_data.get("data", {})
            if isinstance(data_payload, list) and len(data_payload) > 0:
                data_payload = data_payload[0]
            
            if data_payload.get("status") == "error":
                log.error(f"Expo rejected push notification to {push_token}: {data_payload.get('message')}")
            else:
                log.info(f"Successfully sent push notification to {push_token}")
        except Exception as e:
            log.error(f"Failed to send push notification to {push_token}: {e}")
