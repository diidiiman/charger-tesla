import asyncio
import json
import logging
import aiomqtt
from app.db import SessionLocal
from app.schemas import TelemetryWebhookPayload
from app.use_cases.telemetry.process_webhook import ProcessTelemetryWebhookUseCase

log = logging.getLogger(__name__)

# Field mappings between MQTT field names and our payload keys
FIELD_MAPPING = {
    "DetailedChargeState": "charging_state",
    "ChargeState": "charging_state",
    "Soc": "battery_level",
    "EstBatteryRange": "battery_range",
    "IdealBatteryRange": "battery_range", # fallback
    "ChargeAmps": "charger_power", # approximating power from amps or using a different field if needed
    "TimeToFullCharge": "minutes_to_full_charge",
    "ChargeLimitSoc": "charge_limit_soc",
    "Location": "location",
}

async def process_message(topic, payload_str):
    try:
        topic_parts = str(topic).split('/')
        if len(topic_parts) < 4 or topic_parts[2] != 'v':
            return
            
        vin = topic_parts[1]
        field = topic_parts[3]
        
        if field not in FIELD_MAPPING:
            return
            
        # Parse payload
        try:
            value = json.loads(payload_str)
        except json.JSONDecodeError:
            value = payload_str
            
        mapped_field = FIELD_MAPPING[field]
        
        # Build payload
        payload_data = {"vehicle_id": vin}
        
        if mapped_field == "location":
            if isinstance(value, dict):
                payload_data["latitude"] = value.get("latitude")
                payload_data["longitude"] = value.get("longitude")
        elif mapped_field == "minutes_to_full_charge":
             # TimeToFullCharge is often in hours or string format, try to convert to minutes
             try:
                 payload_data[mapped_field] = int(float(value) * 60)
             except (ValueError, TypeError):
                 pass
        else:
            payload_data[mapped_field] = value
            
        payload = TelemetryWebhookPayload(**payload_data)
        
        async with SessionLocal() as db:
            await ProcessTelemetryWebhookUseCase().call(db, payload)
            
    except Exception as e:
        log.error(f"Error processing MQTT message on topic {topic}: {e}")

async def run_mqtt_subscriber():
    log.info("Starting MQTT subscriber")
    
    # Simple reconnect loop
    while True:
        try:
            # We connect to the internal mosquitto broker
            async with aiomqtt.Client("mqtt", port=1883) as client:
                await client.subscribe("telemetry/+/v/#")
                log.info("Subscribed to telemetry/+/v/#")
                
                async for message in client.messages:
                    await process_message(message.topic, message.payload.decode('utf-8'))
                    
        except aiomqtt.MqttError as e:
            log.warning(f"MQTT connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f"Unexpected error in MQTT subscriber: {e}")
            await asyncio.sleep(5)
