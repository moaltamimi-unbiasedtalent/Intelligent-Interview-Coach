# Integrated safety review after PR #265

Reviewed runtime: `aedbef3dee28a68b72bc526a1fca537a3da7bd8d`, merged 23 October 2026. This is an engineering review, not independent security, human, language or hosted qualification. No application code, permission, deployment definition or activation record is changed by this documentation PR.

## Verified integrated behavior

| Area | Code and verification | Result and practical limit |
|---|---|---|
| 01C catalogue | `src/agent/registry.py`, `policies.py`, prompt v1.1.0; `tests/test_tool_registry_parity.py` | Exactly the existing 11 tools; Pydantic schemas and descriptions generate bindings/catalogue; duplicate, invalid registration and drift refused. |
| Authorization scope | `tool_authorization.py`, registry pre-handler path; existing authorization suite | DEFAULT_POLICIES AST is identical to PR #265's parent; tool implementation files are unchanged. No new tool permissions. |
| Streaming admission | `src/api/routes/agent.py` shared admission, owner dependencies and application controls | Authentication, profile/locale/pause/cost checks retained. Foreign and unknown ids receive indistinguishable refusals; cancel remains possible during pause. |
| Events/privacy | `safe_progress` and owner-checked final response | Internal astream_events v2 payloads are consumed privately. Only code-owned event kinds and bounded scalar progress cross SSE; no raw prompt, args, provider callback or exception. Existing candidate-visible final response remains owner-scoped. |
| Stop and deadline | `run_control.py`, agent pre/post-model and pre-tool probes | Durable facts stop later execution and hide late answers. In-flight provider work drains to preserve actual usage; Stop/deadline is not remote request termination. Interrupted shutdown remains explicitly unsettled. |
| Reconnect | GET events reads the same control/checkpoint id; frontend parser and fallback tests | Reconnection does not invoke the graph or replay a POST. Explicit unsupported response before admission permits one synchronous fallback; auth, budget and accepted-stream failures do not. |
| Synchronous compatibility | Existing `/agent/run`, continuation and HITL routes; pre-0048 temporary-store regression | Synchronous paths remain supported; streaming refuses before admission when its control table is absent. This is not a claim that every older application schema is supported. |
| Migration 0048 | Synthetic SQLite rehearsal: 0027 → 0047 → 0048; row preservation, refusal and rollback | Existing 0047 rows preserved; nonempty control-table downgrade refused with revision/data intact; empty downgrade preserved other rows; re-upgrade passed. PostgreSQL execution NOT RUN. |

The targeted backend suites passed **269 tests** (registry/policy, authorization, streaming, usage, async blocking, prompts and migration tests). Three focused frontend files passed **18 tests** (stream parser, Coach and Prepare workspace). These are current local results using installed dependencies, temporary stores and mocks. Historical PR #265 totals are retained in their original evidence; they are not relabelled as a new full run.

## Confirmed blocker and concurrency finding

### POST265-01 — P1: staging migration entrypoint is absent

`deploy/docker-compose.staging.yml` invokes `["bash", "scripts/migrate.sh"]`. There is no `scripts/migrate.sh` in the repository. The real helper is `deploy/scripts/migrate.sh`, and `deploy/Dockerfile.api` copies `scripts/` but not `deploy/scripts/`. The migrate job therefore cannot execute its configured command from this image. API and worker depend on its completion. This is a static path defect, not a failed live deployment; no image was built or started.

Focused remediation PR: make the helper present at the configured image path; prove image file existence and run the exact entrypoint against a disposable database; retain one migration job before API/worker start and no automatic downgrade. Add a regression that resolves Compose commands against image COPY destinations, rather than checking the command string alone. Deployment is blocked until this is fixed and validated.

### POST265-02 — P2: settlement overlap needs a durable admission policy

A deterministic two-service probe shares temporary application/checkpoint stores. It pauses the first producer immediately before usage recording, after its completed checkpoint. Its durable control is still `running`, `settled=false`. A second service instance accepts a continuation and invokes the mocked model again before the first producer settles. Locks are per service instance; `continue_run` checks checkpoint completion and cancellation but not durable settlement.

**Scope of the observation:** the probe made two intended synthetic model invocations, not a reconnect replay. Canonical telemetry correctly retained **2 model calls and 18 tokens** because `record_agent_usage` refuses smaller cumulative replacements. This probe does not establish billing loss, private-data disclosure or duplicate execution through GET reconnect. The default Compose API is a single process; live multi-worker operation remains unqualified.

Focused hardening/qualification PR before multi-worker acceptance: define whether continuation/resume must refuse a still-unsettled producer (recommended: 409), enforce the policy using owner-scoped durable state, and test independent services/processes, late Stop, HITL, telemetry ordering and disposable PostgreSQL. Do not weaken the existing monotonic usage guard or invent zero usage for interrupted work.

## Local database: separate from code readiness

The configured local SQLite database `data/interview_studio.db` is at **0027_email_attempts**, with **21 migrations pending** to 0048; the control table is absent. Only schema/version queries were made against a stable private temporary snapshot, which was removed afterward. The original database was not opened by the migration rehearsal, upgraded or downgraded. The pre-0048 fallback regression uses a schema with the rest of the modern tables; it does not certify this much older local database for the complete current application.

Reproducible engineering observations: `scripts/production/review_post265.py --out <new-report.json>` uses only synthetic temporary stores and mocked models, refuses an existing report path and refuses a runtime differing from its frozen review baseline. [Recorded observations](evidence/POST_PR265_INTEGRATION_2026_10_23.json) include the migration, canonical usage and overlap outcomes.

## Remaining verification boundary

Real PostgreSQL locking, multiple API workers, hosted TLS/proxy buffering, ClamAV/signature lifecycle, live provider timing, graceful shutdown/hard process loss, and backup/restore remain NOT VERIFIED by this review. No language or production gate is approved. See the [staging readiness plan](STAGING_READINESS_PLAN_POST265.md) for the required evidence before activation.
