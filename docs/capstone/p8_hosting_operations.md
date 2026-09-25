# Ask4Mo — Hosting & Operations Runbook (Capstone P8)

Reproducible **STAGING** hosting for Ask4Mo (Intelligent Interview Coach). This
runbook documents the single-replica staging topology, the operational procedures
(migrations, backup, restore, rollback, pause), and the security posture.

> **Honesty note.** These are reproducible **config + docs only**. Nothing here has
> been deployed to a cloud provider, no accounts were created, and no real secrets
> exist in this repo. Anything that can only be proven against a live deployment is
> tracked in the **EX-12 checklist** at the end and is marked **NOT RUN / BLOCKED**.

Artifacts referenced:

| File | Purpose |
|------|---------|
| `deploy/Dockerfile.api` | FastAPI/uvicorn image (Python 3.11, :8000) |
| `deploy/Dockerfile.web` | Next.js 15 image (Node 20, :3000) |
| `deploy/docker-compose.staging.yml` | db / migrate / api / web / caddy topology |
| `deploy/.env.staging.example` | env template (safe placeholders only) |
| `deploy/Caddyfile` | edge TLS termination, HSTS, routing |
| `deploy/scripts/migrate.sh` | `alembic upgrade head` + single-head assertion |
| `deploy/scripts/backup.sh` | pg_dump + documents tar |
| `deploy/scripts/restore.sh` | guarded restore into staging/restore DB |

---

## 1. Architecture

Single-replica staging. TLS terminates at the edge (Caddy); everything else runs on
the internal compose network.

```
                        Internet (443)
                             │
                     ┌───────▼────────┐
                     │     Caddy      │  automatic TLS + HSTS
                     │  edge proxy    │
                     └───┬───────┬────┘
        app.staging.*    │       │   api.staging.*
                 ┌───────▼──┐  ┌─▼──────────┐
                 │   web    │  │    api     │  FastAPI/uvicorn
                 │ Next.js  │  │ src.api.   │  :8000
                 │  :3000   │  │ main:app   │
                 └──────────┘  └───┬────┬───┘
                                   │    │
              /data/documents ◄────┘    │  (mounted volume, private)
                                        │
                                 ┌──────▼──────┐
                                 │ PostgreSQL  │  :5432 (internal only)
                                 │     16      │  named volume db-data
                                 └─────────────┘
                                        ▲
                                 ┌──────┴──────┐
                                 │  migrate    │  one-shot: alembic upgrade head
                                 │ (runs once) │  BEFORE api starts
                                 └─────────────┘
```

**Components**

- **Backend** — FastAPI served by uvicorn, ASGI path `src.api.main:app`, port `8000`.
  Base path `/api/v1`. Liveness `GET /api/health`; readiness `GET /api/v1/ready`
  (DB + config probe, returns **503** when not ready). Python 3.11, deps in
  `requirements.txt` + the `[db]` extra (Alembic + psycopg). Migrations run as a
  **separate step**, never per-replica auto-migrate.
- **Frontend** — Next.js 15 in `frontend/` (Node 20). `npm ci && npm run build`,
  then `npm run start` on port `3000`. Needs `NEXT_PUBLIC_API_BASE_URL` at build and
  run time (e.g. `https://api.staging.example.com/api/v1`). It is a pure client and
  holds no server secrets.
- **Database** — PostgreSQL 16. `DATABASE_URL=postgresql+psycopg://...`. Agent
  checkpoints use `AGENT_CHECKPOINT_DATABASE_URL` (may be the same Postgres).
- **Private file storage** — a mounted volume at `DOCUMENT_STORAGE_DIR=/data/documents`.
  Never a public bucket, never under Next.js public assets. Production-scale option:
  S3-compatible object storage via a document storage adapter.
- **Rate-limit store** — in-memory / process-local (single replica). Multi-replica
  requires a shared store (see §12).
- **Email** — Brevo (`EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, `EMAIL_SENDER`),
  required for open verified-email registration.
- **Realtime voice** — optional, OFF by default (`REALTIME_VOICE_ENABLED`,
  `REALTIME_VOICE_API_KEY`).
- **TLS** — terminated at Caddy, which also sets HSTS. Same-site topology (app + API
  under one parent domain) keeps the session cookie `SameSite=Lax; Secure`.

**Deploy order** (encoded in compose `depends_on`): `db` healthy → `migrate`
completes successfully → `api` healthy → `web` → `caddy`.

```
cp deploy/.env.staging.example deploy/.env.staging   # fill real values
docker compose -f deploy/docker-compose.staging.yml up -d --build
```

---

## 2. Environment matrix

`API_ENV` selects the profile. Validation lives in `src/api/env_validation.py`:
development/test are permissive; **staging and production fail fast** on missing
critical config (production raises `RuntimeError` at boot; staging flags the same
items, with email downgraded to a warning unless open registration is enabled).

Legend: **R** = required, **W** = warning if missing (feature degrades), **o** =
optional, **—** = not applicable.

| Variable | dev | test | staging | production | Notes |
|----------|:---:|:----:|:-------:|:----------:|-------|
| `API_ENV` | R | R | R | R | selects the profile |
| `FRONTEND_ORIGINS` | o | o | **R** | **R** | exact allowlist, no wildcard |
| `APP_BASE_URL` | o | o | **R** | **R** | links, cookies, OIDC redirect |
| `DATABASE_URL` | o (sqlite) | o | **R** (postgres) | **R** (non-sqlite) | sqlite → warn (staging) / fatal (prod) |
| `AGENT_CHECKPOINT_DATABASE_URL` | o | o | W | W | may reuse `DATABASE_URL` |
| `SESSION_SECRET` | o | o | W | W (recommended) | deployment secret |
| `TRUST_PROXY` | o | o | R (behind Caddy) | R | enables correct client IP |
| `OPENROUTER_API_KEY` | W | o | W | W | LLM features unavailable if unset |
| `OPENROUTER_MODEL_FAST/BALANCED/ADVANCED` | o | o | o | o | override model slugs |
| `EMAIL_PROVIDER` / `BREVO_API_KEY` / `EMAIL_SENDER` | o | o | **R\*** | **R\*** | \*required if open registration is on |
| `FEATURE_GOOGLE_LOGIN` (+ `GOOGLE_CLIENT_ID/SECRET`) | o | o | o | o | disables itself if incomplete |
| `REALTIME_VOICE_ENABLED` (+ `REALTIME_VOICE_API_KEY/MODEL`) | o | o | o | o | OFF by default; falls back to turn-based |
| `DOCUMENT_STORAGE_DIR` | o | o | W | W | durable private storage |
| `MALWARE_SCAN_REQUIRED` / `FILE_SCAN_PROVIDER` / `CLAMAV_HOST` / `CLAMAV_PORT` | o | o | R (recommended) | R | fail-closed uploads |
| `RATE_LIMIT_BACKEND` | o | o | o (single replica) | R if multi-replica | `in_memory` default |
| `PAUSED_CAPABILITIES` | o | o | o | o | operator pause switch seed |
| `ADZUNA_APP_ID/KEY`, `EXTERNAL_RESEARCH_ENABLED` | o | o | o | o | current-market research |
| `AGENT_COACH_ENABLED`, `INTERVIEW_LIVE_ENABLED` | o | o | o | o | feature flags |
| `LANGFUSE_PUBLIC_KEY/SECRET_KEY`, `AGENT_EXTERNAL_OBSERVABILITY_ENABLED` | o | o | o | o | telemetry OFF by default |

**Production fail-fast (RuntimeError at boot)** when any of: `FRONTEND_ORIGINS`,
`DATABASE_URL` (non-sqlite), `APP_BASE_URL` is missing, **or** open registration is
enabled without a real email provider. Staging surfaces the same items and stays
strict on CORS/DB/APP_BASE_URL.

---

## 3. HTTPS / TLS

- TLS is terminated **only** at Caddy (`deploy/Caddyfile`), which obtains and renews
  certificates automatically via ACME/Let's Encrypt. Certs/keys persist in the
  `caddy-data` volume.
- The internal `web`/`api` services speak plain HTTP on the compose network and are
  never exposed to the internet directly (compose publishes only 80/443 on caddy).
- Caddy sets **HSTS** (`Strict-Transport-Security: max-age=31536000; includeSubDomains;
  preload`) at the edge. HSTS is owned by the edge; the API does not also emit HSTS
  for browser responses (avoids conflicting `max-age`).
- For dry-run testing without hitting rate limits, the Caddyfile documents switching
  to the Let's Encrypt staging ACME directory.

---

## 4. Cookie topology & CORS

- **Same-site by design.** `app.staging.example.com` (web) and
  `api.staging.example.com` (api) are subdomains of one parent
  (`staging.example.com`). The session cookie is issued by the API as
  **HttpOnly + Secure + SameSite=Lax** (`src/api/routes/auth.py`). Because the app
  and API are same-site, the browser keeps sending the cookie on top-level requests
  from app → API without needing `SameSite=None`.
- Never localStorage, never a request body/URL — the session is an opaque
  server-side token in a cookie only.
- **CORS allowlist.** `FRONTEND_ORIGINS` is a comma-separated **exact** allowlist
  (no wildcard in hosted envs). Set it to the app origin(s). CORS runs with
  credentials, so the origin must match exactly.
- **If you ever split across unrelated domains**, you must switch the cookie to
  `SameSite=None; Secure` and keep a strict CORS allowlist — avoid this in staging;
  prefer the same-parent-domain (or single-domain `/api` path) topology.
- A single-domain path-based alternative (`/api/*` → api on the same host) is
  documented in the Caddyfile and is even simpler for cookies; if used, set
  `NEXT_PUBLIC_API_BASE_URL=https://<app-host>/api/v1`.

---

## 5. Security headers & CSP

- **API self-headers.** The API sets its own strict security headers via
  `SecurityHeadersMiddleware` (`src/api/middleware.py`) on every API response.
- **Page CSP is set at the edge/frontend**, not the API. The Caddyfile ships a
  baseline page `Content-Security-Policy` for the app origin — tighten it to the
  exact hosts you use.
- **Never `connect-src *`.** `connect-src` must explicitly list:
  - the **API origin** for `fetch`/XHR (`https://api.staging.example.com`);
  - the API origin over **`wss://`** if the app opens WebSockets to it;
  - the **realtime voice provider origin** when `REALTIME_VOICE_ENABLED` — e.g.
    `https://api.openai.com wss://api.openai.com` (WebRTC/negotiation reaches the
    provider). Add the exact provider host you configure.
- **Microphone permission.** Realtime WebRTC voice **and** browser speech capture
  need microphone access. The `Permissions-Policy` grants `microphone=(self)` on the
  app origin only; camera/geolocation are denied. Browsers additionally require a
  secure (HTTPS) context and an explicit user grant — both satisfied by the TLS edge.
- Other baseline headers at the edge: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY` (+ CSP `frame-ancestors 'none'`),
  `Referrer-Policy: strict-origin-when-cross-origin`, and `-Server` to avoid
  advertising the upstream.

---

## 6. Private storage

- Uploaded candidate documents live under `DOCUMENT_STORAGE_DIR=/data/documents`, a
  **mounted named volume** (`documents`) attached to the api service only.
- **Never** a public bucket and **never** under the Next.js `public/` assets — files
  are served (if at all) only through authenticated, authorized API routes.
- Production-scale option: an S3-compatible object store behind a document storage
  adapter (private bucket, no public ACLs, server-side encryption). Keep the same
  "never public" invariant.

---

## 7. Health & readiness

- **Liveness** — `GET /api/health` (also `/api/v1/health`). Cheap, no dependencies.
  Used by the container `HEALTHCHECK`. A liveness failure means "restart the
  container."
- **Readiness** — `GET /api/v1/ready` (`src/api/routes/health.py`). Probes DB
  connectivity (`SELECT 1`) and critical config, returns **200** when ready and
  **503 `not_ready`** otherwise — so the edge/load balancer holds traffic during
  startup or a DB blip **without killing** the container. No expensive provider calls.
- The container healthcheck uses **liveness** (not readiness) on purpose, so a
  transient DB outage does not trigger a restart loop.

---

## 8. Database migrations

- **Separate step, run once.** `deploy/scripts/migrate.sh` runs `alembic upgrade
  head` then asserts a **single Alembic head** (`test "$(alembic heads | wc -l)" -eq
  1`), failing if the graph diverged. In compose this is the `migrate` service:
  `restart: "no"`, `depends_on: db healthy`, and `api` waits on
  `migrate: service_completed_successfully`.
- **Never per-replica auto-migrate.** The api image does not migrate on boot. With
  more than one replica, concurrent auto-migration races and can corrupt state; the
  one-shot job guarantees exactly one migrator.
- **Pre-deploy backup is mandatory.** Always run `deploy/scripts/backup.sh` before
  migrating (the script prints this reminder).
- **Failure behaviour.** If `migrate` exits non-zero (upgrade error or >1 head), the
  api service never starts (its dependency is unmet), so a broken migration does not
  ship a half-migrated app. Fix forward and re-run.

---

## 9. Backup

- `deploy/scripts/backup.sh` writes two timestamped artifacts to `BACKUP_DIR`:
  1. **Database** — `pg_dump --format=custom` of `DATABASE_URL`
     (`ask4mo-db-<ts>.dump`).
  2. **Documents** — `tar -czf` of `DOCUMENT_STORAGE_DIR`
     (`ask4mo-documents-<ts>.tar.gz`).
- Credentials come only from the environment (no secrets inline). The SQLAlchemy
  `+psycopg` suffix is stripped for `pg_dump`.
- **Verify** (printed by the script):
  - `pg_restore --list ask4mo-db-<ts>.dump | head` — lists the archive TOC without
    restoring.
  - `tar -tzf ask4mo-documents-<ts>.tar.gz | head` — lists document archive contents.
  - For a full drill, restore into a throwaway `restore` DB (§10).
- Schedule regularly and **immediately before every migration/deploy**.

---

## 10. Restore

- `deploy/scripts/restore.sh` restores a chosen `pg_dump` into `TARGET_DATABASE_URL`
  (`pg_restore --clean --if-exists`) and untars the documents archive into
  `DOCUMENT_STORAGE_DIR`.
- **Guard against clobbering prod:** it refuses unless the target DB name contains
  `staging` or `restore`; override only with explicit `FORCE=1`.
- **Verify** (printed by the script): list tables (`\dt`), spot-check a row count,
  hit `GET /api/v1/ready` against the restored DB, and `ls` the restored documents.
- Practice restores into a `*_restore` database regularly so recovery is proven, not
  assumed.

---

## 11. Rollback

- **App image rollback (safe, preferred).** Re-deploy the previous known-good image
  tags for api/web. Because migrations are a separate step, rolling back application
  code does not roll back the schema.
- **Migrations — forward-fix only.** **Never auto-downgrade a destructive migration.**
  If a migration dropped or rewrote data, a downgrade cannot recreate what was
  deleted. Recover by: (a) restoring from the pre-deploy backup (§10) into a safe DB
  and validating, then (b) shipping a new forward migration that corrects the issue.
- Keep the previous image tags and the pre-deploy backup until the new release is
  verified healthy (readiness green, smoke tests pass).

---

## 12. Operator pause switch

- Costly/external capabilities can be paused without a redeploy.
- **Seed at boot:** `PAUSED_CAPABILITIES` (comma-separated) is read at startup
  (`src/application/pause.py`); a paused capability returns **503** to candidates.
- **Toggle at runtime:** `POST /api/v1/admin/pause/{capability}` (platform-admin
  gated, audited) with `{"paused": true|false}`; `GET /api/v1/admin/pause` reports
  the current state and the pausable set.
- State is process-local (single replica). With multiple replicas it must be backed
  by shared state — same limitation as §13.
- Typical uses: pause `public_registration` (e.g. before email is configured),
  `realtime_voice`, or `external_research`.

---

## 13. Rate limiting

- The app limiter is **in-memory / process-local** (`src/api/rate_limit.py`),
  correct **only for a single replica** — each process has its own counters.
- Client IP honours `X-Forwarded-For` only when `TRUST_PROXY=true` (set behind
  Caddy), so limits apply to the real client, not the proxy.
- **Multi-replica path:** set `RATE_LIMIT_BACKEND=redis` (or provide `REDIS_URL`) and
  supply a shared-store adapter, **or** keep a single replica. Until a shared adapter
  is implemented, run **one replica** in staging.

---

## 14. Malware scanning

- File uploads can be gated by a scanner: `MALWARE_SCAN_REQUIRED=true` +
  `FILE_SCAN_PROVIDER=clamav` (`CLAMAV_HOST`/`CLAMAV_PORT`), see
  `src/documents/file_security.py`.
- **Fail-closed:** when scanning is required and the scanner is unreachable or a file
  is flagged, the upload is **rejected** — the system never accepts an unscanned file
  under a required policy.
- Staging note: run a ClamAV service reachable at `CLAMAV_HOST:CLAMAV_PORT` (a
  `clamav` service can be added to compose) before enabling the required policy, or
  uploads will be refused by design.

---

## 15. Distributed / multi-replica limitations

This staging topology is **single-replica by design**. Before scaling out, the
following process-local state must move to a shared store:

- **Rate limiting** (§13) — needs Redis + a shared adapter.
- **Operator pause switch** (§12) — process-local; needs shared state to apply fleet-wide.
- **In-memory session store** (`InMemorySessionStore`) — verify sessions are backed
  by the database/shared store before running >1 replica.
- **Migrations** already isolated to a one-shot job — keep it that way (never
  per-replica).

Until those are addressed, **run exactly one api replica**.

---

## 16. EX-12 checklist — what still requires an AUTHORIZED deployment

> **EX-12 status: NOT RUN / BLOCKED.** Hosting **cannot be certified from a local
> build**. The items below are provable only against a real, authorized deployment
> (real domain + DNS, ACME-issued certificates, a managed Postgres, and configured
> providers). No cloud account was created and nothing was deployed for this task.

| # | Item to prove | How to prove (once authorized) | Status |
|---|---------------|-------------------------------|--------|
| 1 | TLS + HSTS live | `curl -I https://app.staging.<domain>` shows valid cert + HSTS header | **BLOCKED** |
| 2 | Automatic cert issuance/renewal | Caddy obtains + renews certs for both hosts via ACME | **BLOCKED** |
| 3 | Same-site session cookie | Login sets `HttpOnly; Secure; SameSite=Lax`; app→API calls authenticate | **BLOCKED** |
| 4 | CORS allowlist enforced | Disallowed origin is rejected; `FRONTEND_ORIGINS` origin allowed | **BLOCKED** |
| 5 | Readiness gating | `GET /api/v1/ready` returns 503 pre-DB, 200 once ready | **BLOCKED** |
| 6 | Migration step (single head) | `migrate` job runs once, asserts one head; api waits for it | **BLOCKED** |
| 7 | Backup produces restorable artifacts | `backup.sh` output verified via `pg_restore --list` / `tar -tzf` | **BLOCKED** |
| 8 | Restore drill into `*_restore` DB | `restore.sh` restores + app reaches readiness against it | **BLOCKED** |
| 9 | Rollback | previous image tags redeploy cleanly; forward-fix path exercised | **BLOCKED** |
| 10 | Private storage isolation | documents are not reachable via any public URL / Next.js assets | **BLOCKED** |
| 11 | Pause switch | `POST /api/v1/admin/pause/{capability}` returns 503 to candidates | **BLOCKED** |
| 12 | Email verification flow | Brevo delivers a verification email end-to-end | **BLOCKED** |
| 13 | Malware fail-closed | upload rejected when ClamAV is down under required policy | **BLOCKED** |
| 14 | CSP / mic permissions | page CSP has no `connect-src *`; realtime/browser-speech mic works | **BLOCKED** |
| 15 | Single-replica limits documented + honoured | one api replica; multi-replica blockers (§15) tracked | **DOCUMENTED** |

**Certification statement:** hosting readiness is **not certified**. These artifacts
are reproducible and honest; final certification requires running the EX-12 checklist
against an authorized staging deployment.
