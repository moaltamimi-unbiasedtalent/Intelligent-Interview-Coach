# Operations & Deployment

> **Scope.** This page documents shared environment settings and the legacy Streamlit interface.
> The current product is Next.js + FastAPI: its production authentication is server-side
> accounts and sessions (fail-closed; `API_ENV` selects dev vs non-dev), not Streamlit OIDC. See
> [privacy.md](privacy.md), [../README.md](../README.md) and the deployment artifacts in
> [`../deploy/`](../deploy/) (`.env.staging.example` etc.). Rows marked "legacy Streamlit" below
> do not apply to the FastAPI service.

## Configuration

All configuration is via environment variables or `.streamlit/secrets.toml`
(secrets take precedence). **No secret is ever baked into the image or committed.**

| Setting | Purpose | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | Core interview engine (required) | — |
| `APP_AUTH_REQUIRED` | Require OIDC login (legacy Streamlit interface only) | `false` |
| `DATABASE_URL` | SQLite (dev) / PostgreSQL (prod) | `sqlite:///data/interview_studio.db` |
| `GOOGLE_SPEECH_PROJECT_ID` | Enables Voice (Speech-to-Text) | — |
| `GOOGLE_SPEECH_LOCATION` | Speech region | `global` |
| `GOOGLE_APPLICATION_CREDENTIALS` | ADC for Speech | — |
| `GEMINI_API_KEY` | Enables Live (backend-only; mints ephemeral tokens) | — |
| `GEMINI_LIVE_MODEL` | Live model id | `gemini-3.1-flash-live-preview` |
| `[auth]` (secrets.toml) | Streamlit OIDC provider config (legacy Streamlit interface only) | — |

> **Voice note:** speech features (browser dictation and playback, optional realtime voice, and
> the legacy Streamlit Record/Live paths) are optional and provider-dependent. Realtime voice is
> off by default and has not been validated live. Without credentials the app runs fully on text
> and shows graceful fallbacks.

## Startup validation & health

- `src/health.py` provides `startup_validation(config)` (hard errors vs. soft
  info) and `health_check(config, database_ok=...)`.
- Streamlit's built-in probe `GET /_stcore/health` is used by the Docker
  `HEALTHCHECK`. For a richer readiness signal, surface `health_check(...)`.

## Database & migrations

**Migration ownership.** Local development and tests (SQLite) create tables with
`init_db` → `create_all`. **Production (any non-SQLite database) is schema-owned by
Alembic** — `init_db` no longer calls `create_all` there, so the schema is never
silently created or altered at startup; run migrations explicitly. The baseline
revision `0001_initial` is **immutable**: it uses explicit `op.create_table` /
`op.create_index` operations (it does not import the live model metadata), so a
later model change cannot retroactively alter it. Add schema changes as new
revisions (`alembic revision --autogenerate`), never by editing `0001`.

- Dev/tests: `init_db` creates the SQLite schema automatically.
- Production applies Alembic migrations:
  ```bash
  pip install -e ".[db]"
  DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db alembic upgrade head
  ```

## Docker

```bash
docker build -t intelligent-interview-coach .
docker run --rm -p 8501:8501 \
  -e OPENROUTER_API_KEY=... \
  -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db \
  -e APP_AUTH_REQUIRED=true \
  intelligent-interview-coach
```

Secrets are provided at **runtime** (env or mounted file) — never in the image
(enforced by `.dockerignore`, which excludes `.streamlit/secrets.toml`, `.env`,
`data/`, tests and node_modules). The Live frontend component is not built into
the image by default (Live falls back); build and mount it to enable Live.

## Staging topology (package 05A, code only: DEPLOYMENT FREEZE)

`deploy/docker-compose.staging.yml` defines `db`, `migrate`, `api`, `worker`, `web`, `caddy` and `clamav`
(details and the validation status in `deploy/README-staging.md`). The topology is **not deployed and has
never been started**; it must not be deployed until the owner answers OD-HOSTED and authorises it.

- **Worker:** `python -m src.jobs.worker` from the API image, single replica, after `migrate` and a healthy `db`;
  same `DATABASE_URL`, `COPILOT_DATA_DIR` and `documents` volume as the api. Healthcheck:
  `python -m src.jobs.healthcheck 180`.
- **Data root:** the `knowledge-data` volume is mounted at `/data/knowledge` in both api and worker and
  `COPILOT_DATA_DIR=/data/knowledge` is pinned in both (W12.4A anchoring).
- **Scanner:** the `clamav` service is internal-only (TCP 3310 never published); api and worker use
  `FILE_SCAN_PROVIDER=clamav`. Staging and production refuse `FILE_SCAN_PROVIDER=fake` at boot.
- **Readiness:** the api healthcheck calls `GET /api/v1/ready`; in hosted environments it also reports data-root
  writability (gating) and worker heartbeat and scanner reachability (reported), with no secrets.
- **Backup:** `deploy/scripts/backup.sh` archives the database (`pg_dump`), `documents` and the knowledge data
  root (`COPILOT_DATA_DIR`); `restore.sh` restores all three (`DB_DUMP`, `DOCS_TAR`, `KNOWLEDGE_TAR`).
- **Embeddings:** production must not rely on the hash/local embedder (REVIEW-04 decides the provider).

## CI

`.github/workflows/ci.yml` runs on push/PR:
- **Python:** compile, `pytest` (no live calls), and a secret scan that fails on
  real-looking keys in source.
- **Frontend:** `npm install`, vitest, typecheck, `vite build`.

Browser E2E (Playwright, `e2e/`) is **not** in CI — it needs a live server and
browsers; run it locally (see `e2e/README.md`).

## Transactional email (W12.4C)

- Hosted environments need `EMAIL_PROVIDER=brevo`, a Brevo credential (environment or Admin-managed), `EMAIL_SENDER` set to a sender VERIFIED in Brevo, and `APP_BASE_URL` as an `https://` origin (verification and recovery links use it; production refuses `http://`). Without them a hosted environment uses a not-configured sender that prints nothing and reports `not_configured`; the console adapter is development only.
- Billing (W12.4D-B): `BILLING_PROVIDER` defaults to disabled; `stripe_managed_payments` selects a sandbox FOUNDATION with no checkout and no payments, and live billing is disabled by a code constant (`STRIPE_ENVIRONMENT=live` changes nothing). Store sandbox credentials only in Admin (step-up) or the environment. No migration.
- Google sign-in (when `FEATURE_GOOGLE_LOGIN` is on) needs `OIDC_REDIRECT_URI` set to the exact registered https callback (`.../api/v1/auth/oidc/google/callback`); production refuses to start without it. The flow uses PKCE S256 and validates the ID token.
- A rotated Brevo credential takes effect after the API and the worker restart. Provider acceptance is not delivery; no delivery events are collected. Apply migration `0027_email_attempts` with `alembic upgrade head`. See `docs/capstone/admin/W12_04C_EMAIL_IDENTITY_OPERATIONS.md` for the runbook.

## Invitation-only private beta registration (04E, REQ-BETA-01)

- Staging, production and ANY other `API_ENV` value (unknown labels included) require a valid invitation to register, by password or with a NEW Google account. This is decided from `API_ENV` in code and cannot be switched off by a setting. Local `development`/`dev`/`test`/`testing`/`local` default to NOT requiring one; `REGISTRATION_INVITATION_REQUIRED=true` turns it on locally.
- Apply migration `0042_registration_invitations` with `alembic upgrade head`. Its downgrade refuses while any invitation is pending or redeemed.
- First deployment bootstrap (nobody can register without an invitation, and the Admin console needs an administrator): `python scripts/issue_invitation.py --email owner@example.com --yes` (dry-run without `--yes`; prints the code and link ONCE; set `APP_BASE_URL` first so the link is correct), register with it, verify the email, then `python scripts/bootstrap_admin.py --email owner@example.com --yes`. After that, issue invitations in Admin, Users (`/admin/users`, "Private beta invitations").
- No email is sent for invitations: the operator copies the link (the code is in the URL fragment, so it is not sent to a server or logged). Delivery of invitation emails is a separate decision.

## Secrets handling

- **Admin-managed provider credentials (W12.4B, opt-in).** Set `SECRET_STORE_BACKEND=encrypted_database` and
  `SECRET_STORE_MASTER_KEY` (standard base64 of exactly 32 random bytes, supplied by the deployment, never
  committed, never in the database). Provider credentials set in Admin are then stored only as AES-256-GCM
  ciphertext and override the environment value; removing one restores the environment value. The environment
  is never copied into the database. The master key has no Admin control: rotate it as deployment config.
  Production and staging refuse to start if the backend is selected without a valid key. OpenRouter,
  embeddings, Brevo, Redis and Langfuse credentials take effect after the API and worker restart; Adzuna,
  Google sign-in and realtime voice are read when used. Apply migration `0026_managed_secrets` with the
  normal `alembic upgrade head`. See `docs/capstone/admin/W12_04B_SECURE_PROVIDER_SECRET_ADMINISTRATION.md`.

- Store provider keys only in `.streamlit/secrets.toml` (gitignored) or the
  environment. Never paste keys into chat, logs, or commits.
- The permanent Gemini key stays backend-only; the browser receives only a
  short-lived ephemeral token.
- Google Speech uses Application Default Credentials; the service-account JSON is
  referenced by path and never committed.
