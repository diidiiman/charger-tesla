# Tesla Nord Pool

Threshold-based charging controller for Tesla vehicles, driven by Nord Pool day-ahead electricity prices.

- **Backend** — FastAPI (Python 3.12) + PostgreSQL (Alembic migrations), Tesla Fleet OAuth, encrypted refresh tokens, background scheduler for auto-charging (Pro tier only), and MQTT telemetry subscriber.
- **Mobile** — Expo (React Native, TypeScript). Intro carousel, region picker, Tesla connect, live dashboard, settings, IAP-driven Pro upgrade.
- **Infrastructure** — DigitalOcean Droplet + Managed PostgreSQL. Fully automated deployment via GitHub Actions.
- **Edge** — Caddy reverse proxy with automatic Let's Encrypt cert provisioning for your domain. Cloudflare Worker to proxy Tesla token requests and bypass the WAF.
- **Tesla Middleware** — Official Tesla `fleet-telemetry` server (terminating mTLS) and `vehicle-command` proxy for signing configurations.

```text
┌──────────┐    HTTPS    ┌──────────┐         ┌────────────┐         ┌────────────┐
│ Expo app │ ─────────►  │  Caddy   │ ──────► │  FastAPI   │ ──────► │ Postgres   │
└──────────┘  (auto-SSL) └────┬─────┘         │  backend   │         └────────────┘
       ▲                      │               └─────┬──────┘               ▲
       │ teslacharger://      │                     │ (Auth exchange)      │ (saves live data)
       │                      ▼                     ▼                      │
       │                 ┌──────────┐         ┌────────────┐               │
       │                 │Cloudflare│ ──────► │ Tesla Fleet│               │
       │                 │  Worker  │         │    API     │               │
       │                 └──────────┘         └────────────┘               │
       │                                                                   │
       │                 ┌──────────┐         ┌────────────┐         ┌─────┴──────┐
       └───────────────  │  Tesla   │ ──────► │  Fleet     │ ──────► │   MQTT     │
         telemetry       │ Vehicle  │  mTLS   │ Telemetry  │         │ Subscriber │
         streaming       └──────────┘         └────────────┘         └────────────┘
                              ▲                     ▲
                              │                     │
                         ┌──────────┐               │
                         │ Command  │ ──────────────┘
                         │  Proxy   │ ◄───── (Backend sends telemetry config)
                         └──────────┘
```

---

## Repo layout

```text
.
├── backend/                FastAPI service
│   ├── Dockerfile
│   ├── alembic.ini         DB migrations config
│   ├── entrypoint.sh       runs migrations & boots app
│   ├── requirements.txt
│   └── app/
│       ├── main.py         lifespan + router wiring
│       ├── config.py       pydantic-settings, reads .env
│       ├── db.py           async SQLAlchemy engine + session
│       ├── models.py       User, TeslaAccount, Subscription, OAuthState, ChargeEvent
│       ├── crypto.py       AES-256-GCM for tokens at rest
│       ├── security.py     JWT session tokens + bearer dep
│       ├── tesla.py        Fleet OAuth (PKCE) + REST client + telemetry config
│       ├── prices.py       Nord Pool day-ahead price provider
│       ├── subscriptions.py App Store / Play receipt verification
│       ├── scheduler.py    asyncio loop that drives auto-charging
│       ├── mqtt_subscriber.py Listens to Fleet Telemetry streams
│       └── routes/         auth · tesla_oauth · dashboard · subscription · telemetry
│
├── mobile/                 Expo + React Native (TypeScript)
│   ├── app.json            scheme: teslacharger
│   ├── app/                expo-router screens
│   ├── src/                api, storage, theme, ui components
│   └── .interface-design/system.md
│
├── telemetry/              Fleet telemetry certificates and configs
│   ├── certs/              server.crt & server.key (mTLS for cars)
│   └── server_config.json  Go telemetry server config
│
├── .github/workflows/deploy.yml  DigitalOcean CI/CD pipeline
├── docker-compose.prod.yml       Production docker-compose file
├── docker-compose.yml            Local dev docker-compose file
├── Caddyfile                     auto Let's Encrypt for $PUBLIC_DOMAIN
└── .env.example                  full env template
```

---

## Deployment (DigitalOcean & GitHub Actions)

The stack is designed to be deployed onto a DigitalOcean Droplet with a Managed PostgreSQL database using GitHub Actions.

### 1. Prerequisites

- A DigitalOcean Droplet (Ubuntu/Docker marketplace image).
- A DigitalOcean Managed PostgreSQL database.
- A registered domain (e.g. `charging.yourdomain.com`).
- DNS A-record pointing to your Droplet's IP.
- A free Cloudflare Worker (to bypass Tesla's WAF).
- Tesla Developer Account and registered App.

### 2. Set up Cloudflare Worker (WAF Bypass)

Tesla's WAF (Akamai) frequently blocks DigitalOcean IP addresses from making OAuth token exchanges. We proxy this through a Cloudflare Worker:

1. Create a Cloudflare Worker.
2. Use this script:
   ```javascript
   export default {
     async fetch(request, env, ctx) {
       const targetUrl = 'https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token';
       const newRequest = new Request(targetUrl, {
         method: request.method,
         headers: request.headers,
         body: request.method === 'POST' ? request.body : null,
         redirect: 'follow',
       });
       return fetch(newRequest);
     },
   };
   ```
3. Copy your Worker URL (`https://your-worker.workers.dev`) and set it as `TESLA_AUTH_BASE` in your production environment variables.

### 3. GitHub Actions Secrets

Add the following Secrets and Variables to your GitHub Repository (`Settings -> Secrets and variables -> Actions`):

**Variables (`vars`)**
- `DROPLET_DOMAIN`: The domain of your droplet (e.g., `api.charging.yourdomain.com`).

**Secrets (`secrets`)**
- `DROPLET_SSH_KEY`: The raw private SSH key to access your droplet as root.
- `GOOGLE_CREDENTIALS_JSON`: The raw contents of your Google Service Account JSON.
- `APPSTORE_PRIVATE_KEY_P8`: The raw contents of your Apple App Store Connect P8 key.
- `PROD_ENV_FILE`: The full contents of your `.env` file containing database credentials, encryption keys, and Tesla API tokens. Example:
  ```env
  DATABASE_URL=postgresql+asyncpg://do_user:do_password@db-host:25060/teslacharger?ssl=require
  PUBLIC_DOMAIN=api.charging.yourdomain.com
  ACME_EMAIL=your-email@example.com
  TOKEN_ENCRYPTION_KEY=<random_64_char_string>
  SESSION_JWT_SECRET=<random_64_char_string>
  TESLA_CLIENT_ID=<your_client_id>
  TESLA_CLIENT_SECRET=<your_client_secret>
  TESLA_REDIRECT_URI=https://api.charging.yourdomain.com/callback
  TESLA_AUTH_BASE=https://your-worker.workers.dev
  APPSTORE_BUNDLE_ID=com.clankersystems.charging
  APPSTORE_ISSUER_ID=your_issuer_id
  APPSTORE_KEY_ID=your_key_id
  APPSTORE_USE_SANDBOX=False
  PLAY_PACKAGE_NAME=com.clankersystems.charging
  ```

### 4. Deploy

Any push to the `main` branch will automatically:
1. Copy the codebase to your droplet via SCP.
2. Inject your `.env` and credential files securely.
3. Build and restart the Docker containers.

---

## Tesla Setup & Telemetry

This app uses the **Tesla Fleet API** with Fleet Telemetry for real-time, low-latency streaming of vehicle state without polling.

1. Sign up at <https://developer.tesla.com/>.
2. Create an app. Under **Allowed Redirect URIs** register your callback (e.g., `https://api.charging.yourdomain.com/callback`).
3. Request the scopes: `openid offline_access vehicle_device_data vehicle_location vehicle_charging_cmds vehicle_cmds`.
4. Copy the client id and secret into your `PROD_ENV_FILE` secret.
5. Generate a private key (`com.tesla.3p.private-key.pem`) and derive a public key. The public key must be hosted at `https://your-domain/.well-known/appspecific/com.tesla.3p.public-key.pem`.
6. Once deployed, run the partner registration script on your droplet to register your domain with Tesla:
   ```bash
   docker compose -f docker-compose.prod.yml exec backend python register_partner.py
   ```

When a user authenticates in the app, the backend automatically uses the `vehicle-command` proxy to send a `fleet_telemetry_config` payload to the vehicle, telling it to start streaming data to your `fleet-telemetry` container.

---

## Auto-charging (Pro tier)

`app/scheduler.py` registers an asyncio task on startup that runs every `SCHEDULER_INTERVAL_SECONDS` (default 300). Each tick:

1. Selects users where `auto_charge_enabled` AND a Tesla account is linked AND the subscription row is `active`.
2. For each, fetches the current Nord Pool price for their region.
3. Fetches `charge_state` from the local database (which is constantly updated by the Fleet Telemetry MQTT stream).
4. Decision matrix:
   - plugged in + price ≤ threshold + not currently charging → `charge_start`
   - plugged in + price > threshold + currently charging → `charge_stop`
   - otherwise → no-op
5. Logs every decision (action, price, threshold, detail) to `charge_events`.

Free-tier users are excluded — they get manual controls only.

---

## Subscriptions

Both store integrations follow the same pattern: the client buys via `react-native-iap`, sends the receipt to `POST /v1/subscription/verify`, and the backend authoritatively decides whether to flip `subscription.active`.

- **Android** — The backend uses the `google-auth` library and the injected Google Service Account JSON to exchange tokens and verify the subscription expiration time via the Play Developer API.
- **iOS** — To wire in real verification, build a JWT with the P8 key (`APPSTORE_KEY_ID`, `APPSTORE_ISSUER_ID`, `APPSTORE_BUNDLE_ID`), POST to `/inApps/v1/transactions/{transactionId}`, then read `expiresDate`. (Currently uses a stub verifier if `STUB_ALLOW_ALL = True`).

---

## Price provider

Default: Nord Pool's public `dataportal-api`, day-ahead prices in EUR/MWh, divided by 1000 to yield EUR/kWh. Free, no auth, covers NO1–5, SE1–4, DK1–2, FI, EE, LV, LT.

Swap by setting `PRICE_PROVIDER` in `.env` and adding a branch in `prices.current_price()`. The `prices.REGIONS` list defines the choices the mobile app shows.

---

## License

Private / proprietary.
