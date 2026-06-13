import httpx
import logging

log = logging.getLogger(__name__)

async def send_push_notification(push_token: str, title: str, body: str, data: dict = None):
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
            log.info(f"Successfully sent push notification to {push_token}")
        except Exception as e:
            log.error(f"Failed to send push notification to {push_token}: {e}")
