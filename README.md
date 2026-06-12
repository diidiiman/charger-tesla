# Tesla Charger

Threshold-based charging controller for Tesla vehicles, driven by Nord Pool
day-ahead electricity prices.

- **Backend** — FastAPI (Python 3.12) + PostgreSQL, Tesla Fleet OAuth, encrypted
  refresh tokens, background scheduler for auto-charging (Pro tier only).
- **Mobile** — Expo (React Native, TypeScript). Intro carousel, region picker,
  Tesla connect, live dashboard, settings, IAP-driven Pro upgrade.
- **Edge** — Caddy reverse proxy with automatic Let's Encrypt cert provisioning
  for `charging.clankersystems.com`.

```
┌──────────┐    HTTPS    ┌──────────┐         ┌────────────┐
│ Expo app │ ─────────►  │  Caddy   │ ──────► │  FastAPI   │
└──────────┘  (auto-SSL) └──────────┘         │  backend   │
       ▲                                       └─────┬──────┘
       │ teslacharger:// deep-link                   │
       │ (post-OAuth callback)                       ▼
       │                                       ┌──────────┐
       └────────── Tesla Fleet API ────────►   │ Postgres │
                                                └──────────┘
```

---

## Repo layout

```
.
├── backend/                FastAPI service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py         lifespan + router wiring
│       ├── config.py       pydantic-settings, reads .env
│       ├── db.py           async SQLAlchemy engine + session
│       ├── models.py       User, TeslaAccount, Subscription, OAuthState, ChargeEvent
│       ├── crypto.py       AES-256-GCM for tokens at rest
│       ├── security.py     JWT session tokens + bearer dep
│       ├── tesla.py        Fleet OAuth (PKCE) + REST client
│       ├── prices.py       Nord Pool day-ahead price provider
│       ├── subscriptions.py App Store / Play receipt verification (stub)
│       ├── scheduler.py    asyncio loop that drives auto-charging
│       └── routes/         auth · tesla_oauth · dashboard · subscription
│
├── mobile/                 Expo + React Native (TypeScript)
│   ├── app.json            scheme: teslacharger
│   ├── app/                expo-router screens
│   │   ├── _layout.tsx     Stack navigator
│   │   ├── index.tsx       boot router (intro / region / connect / dashboard)
│   │   ├── intro.tsx       4-page onboarding
│   │   ├── region.tsx      Nord Pool area + threshold
│   │   ├── connect.tsx     Tesla OAuth launcher
│   │   ├── auth.tsx        deep-link landing
│   │   ├── dashboard.tsx   live price + SoC + start/stop
│   │   ├── settings.tsx    region & threshold edit, unlink Tesla
│   │   └── upgrade.tsx     Pro IAP
│   ├── src/
│   │   ├── theme.ts        design tokens (Precision & Density)
│   │   ├── api.ts          typed fetch client
│   │   ├── storage.ts      SecureStore wrapper
│   │   └── components/ui.tsx
│   └── .interface-design/system.md  design-system source of truth
│
├── docker-compose.yml      caddy + backend + postgres
├── Caddyfile               auto Let's Encrypt for $PUBLIC_DOMAIN
├── .env.example            full env template
└── .gitignore              excludes all .env*, secrets/, pgdata/, expo caches
```

---

## Quickstart (dev)

### Prerequisites

- Docker + Docker Compose
- A registered Tesla Fleet API app (see *Tesla setup* below)
- An A/AAAA record pointing `charging.clankersystems.com` → your server
- Node.js 20+ and `npx expo` for the mobile app

### 1. Configure

```bash
cp .env.example .env
# Edit .env: TESLA_CLIENT_ID, TESLA_CLIENT_SECRET, TESLA_REDIRECT_URI,
# TOKEN_ENCRYPTION_KEY, SESSION_JWT_SECRET, POSTGRES_PASSWORD, ACME_EMAIL
python -c "import secrets; print(secrets.token_hex(32))"        # → TOKEN_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"     # → SESSION_JWT_SECRET
```

### 2. Bring the backend up

```bash
docker compose up -d --build
docker compose logs -f backend caddy
```

On first boot Caddy will request a Let's Encrypt cert for `$PUBLIC_DOMAIN`.
The DNS record must already resolve to the host, and ports 80 + 443 must be
reachable from the public internet (Let's Encrypt's HTTP-01 challenge runs on
port 80).

Once up:

- `https://charging.clankersystems.com/health` returns `{"ok": true}`
- `https://charging.clankersystems.com/docs` serves the OpenAPI explorer

Tables are auto-created on startup via SQLAlchemy `metadata.create_all`. For
production, swap in Alembic migrations (see *Roadmap* below).

### 3. Run the mobile app

```bash
cd mobile
npm install
EXPO_PUBLIC_API_BASE=https://charging.clankersystems.com npx expo start
```

Press `i` for the iOS simulator or `a` for Android. Scan the QR code in
Expo Go to run on a physical device (note: native IAP requires an EAS dev
client, not Expo Go).

---

## Tesla setup

This app uses the **Tesla Fleet API**, not the older third-party "ownerapi"
flow (which Tesla has retired).

1. Sign up at <https://developer.tesla.com/>.
2. Create an app. Under **Allowed Redirect URIs** register:
   `https://charging.clankersystems.com/auth/tesla/callback`
3. Request the scopes:
   `openid offline_access vehicle_device_data vehicle_charging_cmds vehicle_cmds`
4. Copy the client id and secret into `.env`.
5. Pick the regional Fleet API base — NA/APAC: `fleet-api.prd.na.vn.cloud.tesla.com`,
   EU/MEA: `fleet-api.prd.eu.vn.cloud.tesla.com` — and set `TESLA_API_BASE`.

> **Vehicle-command signing.** Tesla now requires post-2021 vehicles to receive
> commands through the `vehicle-command` HTTP proxy after pairing a virtual key.
> If `charge_start` / `charge_stop` returns 412 or "vehicle requires key pairing",
> deploy the Go [`vehicle-command`](https://github.com/teslamotors/vehicle-command)
> binary as a sidecar and point `TESLA_API_BASE` at it. Pre-2021 Model S/X and
> some other models still accept direct Fleet REST commands.

---

## Authentication model

There are two distinct tokens in the system:

| Token                 | Issued by | Stored where           | Lifetime  | Purpose                                |
| --------------------- | --------- | ---------------------- | --------- | -------------------------------------- |
| Session JWT (HS256)   | backend   | mobile `SecureStore`   | 30 days   | Authenticates the mobile app → backend |
| Tesla refresh token   | Tesla     | postgres, AES-256-GCM  | months    | Lets the backend mint Tesla access tokens |
| Tesla access token    | Tesla     | postgres, AES-256-GCM  | 8 hours   | Bearer for Fleet API calls             |

The mobile app generates a UUID on first install (stored in `SecureStore`) and
trades it for a session JWT at `POST /v1/auth/device`. That JWT is sent on
every subsequent request as `Authorization: Bearer …`.

The Tesla OAuth flow:

1. App calls `POST /auth/tesla/start` → backend mints a PKCE pair, persists
   `(state, code_verifier)` bound to the user, returns the Tesla `authorize_url`.
2. App opens that URL in a WebBrowser session.
3. After login, Tesla redirects to
   `https://charging.clankersystems.com/auth/tesla/callback?code=…&state=…`.
4. The callback handler looks up the PKCE row by `state`, exchanges the code +
   verifier for tokens, encrypts and stores them, then issues a 302 to
   `teslacharger://auth?ok=1`.
5. The mobile app's deep-link handler routes back to `/dashboard`.

Tesla refresh happens transparently in `tesla.get_access_token()` — every
Fleet API call goes through it.

---

## Backend HTTP surface

All routes return JSON. Routes under `/v1/*` require `Authorization: Bearer …`.

| Verb   | Path                          | Description                                           |
| ------ | ----------------------------- | ----------------------------------------------------- |
| GET    | `/health`                     | Liveness probe                                        |
| GET    | `/docs`                       | OpenAPI explorer                                      |
| POST   | `/v1/auth/device`             | Register/lookup device id, return session JWT         |
| POST   | `/auth/tesla/start`           | Begin Tesla OAuth, returns `authorize_url`            |
| GET    | `/auth/tesla/callback`        | OAuth redirect target (302 → deep link)               |
| POST   | `/auth/tesla/unlink`          | Forget stored Tesla tokens                            |
| GET    | `/v1/regions`                 | Nord Pool delivery areas                              |
| GET    | `/v1/settings`                | Current user settings                                 |
| PUT    | `/v1/settings`                | Update region / threshold / auto_charge_enabled       |
| GET    | `/v1/price`                   | Current Nord Pool price for the user's region         |
| GET    | `/v1/dashboard`               | One-shot bundle: settings + vehicle + charge + price  |
| POST   | `/v1/charge/start`            | Manual charge start                                   |
| POST   | `/v1/charge/stop`             | Manual charge stop                                    |
| POST   | `/v1/charge/wake`             | Wake the vehicle                                      |
| GET    | `/v1/subscription`            | Current subscription status                           |
| POST   | `/v1/subscription/verify`     | Submit an IAP receipt; backend validates & persists   |

---

## Auto-charging (Pro tier)

`app/scheduler.py` registers an asyncio task on startup that runs every
`SCHEDULER_INTERVAL_SECONDS` (default 300). Each tick:

1. Selects users where `auto_charge_enabled` AND a Tesla account is linked AND
   the subscription row is `active`.
2. For each, fetches the current Nord Pool price for their region.
3. Fetches `charge_state` from Tesla.
4. Decision matrix:
   - plugged in + price ≤ threshold + not currently charging → `charge_start`
   - plugged in + price > threshold + currently charging → `charge_stop`
   - otherwise → no-op
5. Logs every decision (action, price, threshold, detail) to `charge_events`.

Free-tier users are excluded — they get manual controls only.

---

## Subscriptions (€4/mo)

Both store integrations follow the same pattern: the client buys, sends the
receipt to `POST /v1/subscription/verify`, and the backend authoritatively
decides whether to flip `subscription.active`.

The current `subscriptions.py` is a structured stub — it accepts any non-empty
receipt while `STUB_ALLOW_ALL = True`. To wire in real verification:

- **iOS** — App Store Server API. Build a JWT with the P8 key
  (`APPSTORE_KEY_ID`, `APPSTORE_ISSUER_ID`, `APPSTORE_BUNDLE_ID`), POST to
  `/inApps/v1/transactions/{transactionId}`, then read `expiresDate`.
- **Android** — Play Developer API. Load the service-account JSON
  (`PLAY_SERVICE_ACCOUNT_JSON_PATH`), request a token for
  `androidpublisher` scope, GET
  `/applications/{package}/purchases/subscriptionsv2/tokens/{purchaseToken}`,
  then read `lineItems[*].expiryTime`.

Flip `STUB_ALLOW_ALL = False` once both are live. If a subscription lapses,
`auto_charge_enabled` is automatically cleared on the next verify.

---

## Price provider

Default: Nord Pool's public `dataportal-api`, day-ahead prices in EUR/MWh,
divided by 1000 to yield EUR/kWh. Free, no auth, covers NO1–5, SE1–4, DK1–2,
FI, EE, LV, LT.

Swap by setting `PRICE_PROVIDER` in `.env` and adding a branch in
`prices.current_price()`. The `prices.REGIONS` list defines the choices the
mobile app shows.

> The original spec mentioned a "Norstat" electricity price API; that
> doesn't appear to be a real product. Nord Pool is the closest match for the
> region it covers. Replace if you have a different provider in mind.

---

## Design system

The mobile UI is built per the `interface-design` skill convention
(<https://github.com/Dammyjay93/interface-design>). The chosen direction is
**Precision & Density** — dark monochrome, single Tesla-red accent, borders
over shadows, tabular numerics. All tokens live in `mobile/src/theme.ts`;
the human-readable system spec is in `mobile/.interface-design/system.md`.

---

## Roadmap before production

- Replace `Base.metadata.create_all` with **Alembic** migrations.
- Real IAP receipt verification (flip `STUB_ALLOW_ALL = False`).
- Vehicle-command signing proxy for newer Teslas.
- Per-user rate limiting on Tesla API calls (Fleet API has tight quotas).
- Push notifications when auto-charging triggers.
- Move the JWT secret to a real KMS, rotate `TOKEN_ENCRYPTION_KEY` via dual-key
  envelope.

---

## License

Private / proprietary.
