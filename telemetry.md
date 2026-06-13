# Fleet Telemetry Migration Guide

This guide explains how to complete the setup of Tesla Fleet Telemetry for your production app. The Python backend has already been fully rewritten to depend on this streaming architecture (reducing your Tesla REST API data polling to literally 0 requests)!

## 1. Prerequisites
To get vehicles to securely stream data to your server, you must have completed Partner Registration and hosted the `com.tesla.3p.public-key.pem` on your domain (which we have already done!).

## 2. Infrastructure Deployment
Tesla vehicles do not natively speak simple HTTP webhooks. They stream binary Protocol Buffers (`protobufs`) over Mutual TLS (mTLS) WebSockets.

Because of this, you must run Tesla's official Go server as a middleware component in your cloud environment:
1. Review the [Tesla Fleet Telemetry GitHub repository](https://github.com/teslamotors/fleet-telemetry).
2. Deploy the `teslamotors/fleet-telemetry` docker container.
3. Terminate mTLS traffic on a Load Balancer (or NGINX) directly into this Go server.

## 3. Data Dispatching
The Go server decodes the binary protobufs coming from the cars. You need to configure the Go server to forward this decoded data to your Python backend.

1. In the Go server's `config.json`, configure a backend Dispatcher (e.g., Kafka, Google PubSub, or MQTT).
2. Set the `transmit_decoded_records` flag to `true` in the Go config so it outputs clean JSON instead of binary protobufs.
3. Write a small worker (or configure an HTTP sink on your PubSub broker) to `POST` the JSON packets directly to your Python backend at:
   ```
   POST https://your-backend-url.com/v1/telemetry/webhook
   ```

The Python backend will automatically parse the `TelemetryWebhookPayload`, cache the live `battery_level`, `charging_state`, and `location` in the `VehicleState` database table, and the mobile dashboard will instantly reflect these changes!

## 4. Configuring Vehicles
The final step is to tell each individual user's car to actually start streaming the data to your server.

This requires sending a `fleet_telemetry_config` payload to the car. Because this payload must be cryptographically signed by your private key (`com.tesla.3p.private-key.pem`), you must deploy Tesla's [Vehicle Command Proxy](https://github.com/teslamotors/vehicle-command).

Once deployed, your Python backend or an admin script can trigger the configuration to the vehicle containing the specific fields you need (e.g., `Location`, `ChargeState`, `DetailedChargeState`) and the URL of your new Go WebSocket server.
