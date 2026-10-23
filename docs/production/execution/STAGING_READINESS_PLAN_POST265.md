# Gap-based staging readiness plan after PR #265

Baseline: main `aedbef3dee28a68b72bc526a1fca537a3da7bd8d`. **Planning and offline inspection only. No deployment, cloud provisioning, provider round trip, paid evaluation, DNS change or real database migration is authorized or performed here.** Existing definitions are retained; this plan does not rebuild the application.

## 1. Existing systems and concrete gaps

| System | Existing implementation | Gap and next evidence |
|---|---|---|
| PostgreSQL | Compose `db` PostgreSQL 16, internal port, durable volume; `[db]` includes psycopg and official PostgreSQL checkpoints | Disposable PostgreSQL migration/locking/worker/checkpoint proof is NOT RUN locally. Confirm app and checkpoint store placement and include both in backup if separated. |
| Migrations | One-shot `migrate`, API/worker depend on it; 48 linear revisions | **POST265-01 P1:** configured helper path is missing from the image. Fix and test the exact entrypoint before deployment. |
| API/web/edge | Non-root API, Next.js, Caddy TLS/HSTS, exact-origin CORS, private documents/knowledge volumes | Provider, region, domains, DNS, certificates, persistent-volume permissions and image builds are unverified. CSP/browser behavior and SSE flush through the actual proxy need evidence. |
| Redis | Runtime adapter and 05D verification helper exist | Compose has no Redis service; template selects in-memory limiting; no direct Redis client dependency is declared in pyproject/requirements. Choose managed/internal Redis and a pinned client build. Runtime outage currently falls back to per-process limiting: OD/owner failure policy must be recorded, not described as distributed fail-closed. One replica is not multi-worker qualification. |
| Worker | Single `src.jobs.worker`, shared DB/documents/knowledge, heartbeat healthcheck | Prove heartbeat freshness, SKIP LOCKED/idempotency, retries, restart and shared volume behavior on PostgreSQL. Keep one worker until qualified; reconcile 30-second worker grace with approved operation timeouts and drain policy. |
| ClamAV | Internal-only daemon, persistent signatures, API/worker pin same scanner/data root; uploads fail closed | Real daemon/image/signature update, EICAR refusal, outage, stale signatures and recovery are NOT RUN. Readiness reports scanner/worker without making either a traffic gate; add operator alert/acceptance checks. |
| OpenRouter/budget | Governed model catalogue, encrypted managed credentials, 05C SQL ledger and worst-case reservation; unknown usage retained | Template omits AI_BUDGET_MODE/config/approval-marker wiring. Set enforcement and fresh owner-approved ceilings/pricing/limits before any live AI. Missing configuration must refuse calls; no old EUR/USD allowance is reusable. No calls during readiness inspection. |
| Knowledge/embedding | Shared knowledge volume, manifests, governed source filters, fail-closed hosted retrieval | Empty volume is not an index. OD-EMBED benchmark/model/dimensions/index compatibility and approved per-market licences are missing. Do not enable lexical/hash fallback or seed unapproved evidence to pass a smoke test. |
| Monitoring | `/health`, `/ready`, worker heartbeat, scanner status, Admin alerts and budget status | Need live baselines, alert/outage/recovery drills, named on-call and response thresholds. A ready response checks DB connectivity/config/data-root, not proof of every schema, scanner or worker requirement. External telemetry stays off unless separately approved and privacy reviewed. |
| Backup/recovery | Checked/signed/sealed backup-set, erasure ledger, restore/rollback tooling and offline records | Compose has no backup/restore runner or immutable tag pointer; API image lacks pg_dump/pg_restore. Existing shell tar/pg_dump helpers alone are not a consistent sealed set. Provide client tools, off-host encrypted destination, keys/escrow, isolated restore target, retention process and real drills. |
| Languages | 06H activation validator and seven review packs | All seven locales have 0/14 approved gates. Hosted candidate journeys must remain refused until valid records exist. OD-STAGING-LANGUAGES requires a decision; do not change API_ENV to disguise an unqualified hosted run. An isolated development-class synthetic exercise, if approved, is not hosted qualification. |
| SSE | Authenticated progress/Stop/reconnect and old-schema fallback merged | Qualify gateway buffering, idle timeout, disconnect/Stop, actual usage drain, process loss and PostgreSQL ownership. Resolve POST265-02 admission policy before multi-worker acceptance. |

## 2. Owner decisions required before authorized staging

- OD-HOSTED: provider/region, environment isolation, allowed domains, infrastructure budget, who may provision and an explicit staging authorization. Production remains a separate authorization.
- OD-RESOURCE, OD-LANG-03/04, OD-HELDOUT-AUTHOR: name operations/security owners, seven native reviewers, counsel/legal qualifiers, licensing reviewer and independent AI evaluators; assign dates and sign-off responsibilities.
- OD-BUDGET: fresh bounded evaluation/provider ceilings, allowed model ids/hosts/categories, output/input limits, timeout/retry/concurrency limits, new ledger and approved marker. Verify current pricing only when preparing an authorized paid run. No guessed costs or inherited capstone credit.
- OD-EMBED, OD-COVERAGE, OD-US-CONTENT, OD-LANG-02 and OD-GATE-THRESHOLDS: production embedding choice, qualified markets/sources, frozen beta coverage, evaluation and latency/availability/RTO/RPO thresholds.
- OD-STAGING-LANGUAGES and OD-APPROVED-UNTIL: qualification order and release-SHA/expiry binding. Preserve the fail-closed implementation; no fabricated approval record.
- Identity/product policy: invitation issuer/email, Google enabled-versus-disabled verification, Redis outage policy (H-REDIS-POLICY), tier limits, bulk actions, ownership transfer and export-format approvals remain open despite their engineering implementations.
- Privacy/support: provider data-handling review, retention/deletion/backup window, key custody, support/on-call ownership and incident response. This plan grants no legal approval.

## 3. Ordered implementation and migration sequence (future authorized work)

1. **Focused remediation PRs first:** repair the migration image entrypoint (POST265-01), add missing immutable image/backup/restore/Redis/budget wiring as applicable, and resolve POST265-02 before adding API workers. Test changes offline; no automatic deploy or merge.
2. Select a reviewed release SHA and build/tag API, worker, migrate and web images once. Record digests, dependency manifests, prompts, activation-record hash and topology. The present Compose `build:` setup lacks this rollback pointer.
3. Provision only the authorized isolated staging network, private storage, secret manager and off-host backup destination. Expose only TLS edge; keep PostgreSQL, Redis, worker and ClamAV private. Keep credentials server-side and stable encryption/master keys available to approved operators only.
4. Take and verify a sealed/signed pre-migration backup set for any existing target. Drain API admissions and workers so files, database, knowledge/index and any separate checkpoint store form one consistent unit; retain an independently protected erasure ledger. Do not import a developer database or real candidate data as test fixtures.
5. For a fresh PostgreSQL target apply **0001 through 0048 once** via the repaired migrate service, then verify actual `alembic_version` equals the single code head. For an existing target apply only its missing ordered revisions after rehearsal on a disposable copy. The permanent local DB is at 0027: its separate repair would require 0028–0048 after backup/rehearsal and explicit authorization; it is not migrated by this task.
6. Restore/build approved knowledge and its matching embedding manifest before retrieval. Start API and the single worker only after migrations and dependency checks succeed; start web/edge afterward. Validate configuration, source approval and language records before admitting candidate traffic.
7. Run infrastructure and safe refusal checks with public/synthetic fixtures. Provider round trips, email/OIDC, scanner test uploads and live evaluations are separate authorized steps. No language becomes active because a container is healthy.
8. Record SHA/digests, UTC times, topology, commands, observations, provider receipts, redacted logs and drill artifacts. Keep failed and partial outcomes. Only named approvers may accept gates; CI cannot approve legal, language or human evidence.

## 4. Health, security and privacy checklist

- `/api/v1/health` and `/api/health`: liveness only. `/api/v1/ready`: connectivity/config/data-root. Explicitly verify schema head and private volume persistence as separate checks; a SELECT 1 cannot prove schema currency.
- Worker: heartbeat within the configured threshold (Compose checks 180 seconds); scanner reachable with current signatures. Alert and test outage/recovery even though these dependency status words do not remove API readiness.
- `/api/v1/capabilities`: streaming available only with migration/control table; hosted qualified locales remain empty until all approvals exist. Missing/expired/mismatched approval must refuse traffic. Keep Russian, live billing, disabled speech and other deferrals disabled.
- Two owned synthetic users: foreign/missing run ids, documents, stories and shares refuse identically; Admin cannot read private candidate content. Verify deletion including control rows, checkpoints, files and erasure after restore.
- SSE: fresh run, GET reconnect without POST replay, bounded Last-Event-ID, safe metadata, heartbeat/proxy flush, stop before/after model completion, deadline and process-loss unknown usage, and durable continuation admission across workers.
- Exact CORS/cookie/TLS/forwarded-header policy; no development impersonation headers accepted in staging; credentials, prompt/raw events and candidate content excluded from logs/monitoring. In-app budget and incident alerts stay useful when external telemetry is off.

## 5. Rollback and recovery

Prefer a forward fix. Freeze admissions, drain work, preserve usage reservations and record unresolved calls rather than writing zero cost. Point API/worker/web to a tested previous immutable image only if it tolerates the current schema. Never rerun migration jobs automatically on an application rollback.

Migration 0048 refuses downgrade when `agent_run_controls` contains rows. Do not delete real control rows to force rollback. If downgrade is unsafe, restore a verified pre-migration set to a **new, empty** database/volumes and repoint after checks; retain the original for recovery. Verify schema, document/knowledge/index hashes and retrieval parity; reapply the independent erasure ledger so deleted users are not resurrected. Preserve secret-store master keys and backup encryption/signing keys outside the restored DB. The current Compose needs tag pointers and a safe restore profile before this procedure is executable.

## 6. Existing scripts and authorized live checks

| Existing entrypoint | Intended verification | Authorization/evidence boundary |
|---|---|---|
| `scripts/eval_hosting_readiness.py`, `tests/test_staging_topology_05a.py` | Offline config/topology/readiness contracts | Not a deployment or image-content proof; add the missing-helper regression. |
| `deploy/scripts/migrate.sh` | Migration wrapper in source | Current image/Compose path is broken; fix before invoking it in a deployment. |
| `tests/test_pg_05b.py`, migration/worker/authorization suites | Disposable PostgreSQL claims, rollback, audit/secret behavior | Requires an explicitly disposable TEST_DATABASE_URL; not run against the local or production DB. |
| `scripts/verify_identity_live_05d.py` | OIDC config/start/finish, email round trip, webhook probes, Redis semantics | Live subcommands require staging, explicit flag and LIVE_VERIFY_AUTHORISED marker; recipient/test account and provider authorization must be supplied. |
| `scripts/backup_set.py`, `scripts/restore_drill.py`, `scripts/rollback_rehearsal.py` | Verify sealed backup, restore/refusal/tamper/erasure and rollback | Dry-run or synthetic first; execute only against approved targets, never reuse live volumes for a drill. |
| `scripts/production/sample_ocr_07c.py` | Real OCR on synthetic images/PDFs | Repeat in the authorized target image, with a frozen representative/noisy corpus and agreed review criteria; local clean samples alone do not qualify hosted quality. |
| `scripts/eval_ragas.py`, `scripts/p10e_live.py`, `scripts/eval_agent_live.py` | 07B grounding and agent-policy evaluation | Fresh owner scope/budget, mandatory governor/ledger, synthetic/public data, frozen hashes; no live/allow-paid flag used now. |
| `frontend/e2e` real-stack journey mode plus SSE HTTP contract tests | Per-language Candidate journey and recovery | Mocked GitHub browser tests are engineering evidence. Hosted per-language evidence still requires actual qualified records and the agreed staging protocol. |

## 7. Evidence bundles required by the requested gates

| Gate | Required evidence before acceptance |
|---|---|
| PG-01 | Owner hosting authorization; release SHA/image digests; TLS/HSTS/CORS/cookie/refusal probes; secret handling; repeatable migration, health and clean-environment rehearsal. |
| PG-02 | Invitation-only rejection/acceptance; authorized Brevo verification and recovery round trips; session revocation/deletion; Google validated or demonstrably disabled; shared-limiter and outage-policy evidence. |
| PG-03 | Frozen independent injection corpus by language/category, approved thresholds, detection/benign-FP results, tool reauthorization and cross-user negatives; named security review; 07B guarded live policy results. |
| PG-05 | Matching embedder/index manifests; licensed per-market sources; real malware/refusal/signature checks; PostgreSQL/volumes restart and separate restore; retrieval/citation/coverage evidence with unknowns explicit. |
| PG-06 | Qualified per-language real-stack browser journeys including Start Interview; SSE progress/Stop/reconnect/deadline/process-loss and usage proof through the real proxy; continuation policy; outage/latency results at approved thresholds. |
| PG-09 | API/worker/scanner/provider/index alerts and recovery; signed/encrypted backup plus off-site retention/erasure; real PostgreSQL restore and application/prompt rollback; measured RTO/RPO and named on-call. |

## 8. Stop/go boundary

Ready to prepare focused PRs and owner decisions; **not ready to deploy this unchanged topology**. Stop before provisioning/deployment and before any live paid evaluation until separate explicit authorization and the required inputs exist. Passing offline tests does not remove these blockers.
