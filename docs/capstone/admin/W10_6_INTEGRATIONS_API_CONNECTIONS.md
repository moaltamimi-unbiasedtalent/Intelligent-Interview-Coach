# P10B-W10.6 - Integrations & API Connections

**Status:** implemented on branch `feat/p10b-w10-6-integrations-api-connections`; **complete when merged to `main`**. **W10.9 is NOT STARTED.**
One small additive migration (`0017_integrations`). No new dependency. 0 paid/live calls. **Secret values are never retrievable.**

## 1. Starting point
`main` `a3535e5d8c7e93d8b72b53b26b2496750237d9bc` (W10.4 complete), clean tree, Alembic head `0016_plans_entitlements`.

## 2. Branch
`feat/p10b-w10-6-integrations-api-connections`.

## 3. External-integration audit
Derived from the code (environment reads and provider modules), not assumed.
| Integration | Code support | Credential source | Runtime-enabled? | Live-validated? | Admin action before | W10.6 action |
|---|---|---|---|---|---|---|
| OpenRouter (chat models) | `openrouter_client.py`, `copilot/llm/openrouter.py` | `OPENROUTER_API_KEY` (secrets file, then environment) | when the key is set | not by this wave | boolean on `/admin/providers` | registry, status, manual key-information test |
| OpenAI embeddings (optional) | `copilot/embeddings.py` (local embedder is the default) | `COPILOT_EMBEDDING_API_KEY` | when keyed and not `local` | no | none | status only |
| Realtime voice | `voice/realtime.py` | `REALTIME_VOICE_API_KEY` + `REALTIME_VOICE_ENABLED` | off by default | NOT RUN | booleans | status only |
| Adzuna | `copilot/research/adzuna_provider.py`, `knowledge/providers/adzuna.py` | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | when keyed | cost-gated, UNVALIDATED | boolean | status only (no probe: it consumes quota) |
| Google OIDC | `application/oidc.py` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` + `FEATURE_GOOGLE_LOGIN` | off by default | not validated, not wired into candidate sign-in | boolean | status only |
| Brevo email | `mail/sender.py` | `BREVO_API_KEY`, `EMAIL_SENDER`, `EMAIL_PROVIDER` | console by default | no live delivery validated; support replies are never emailed | raw provider echo (fixed in W10.1) | status only |
| Redis rate limiting | `api/rate_limit.py` | `REDIS_URL` (carries credentials), `RATE_LIMIT_BACKEND` | in-memory by default; `redis` package not installed | fake client only: NOT LIVE | boolean | status only |
| Langfuse | `observability/` | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` + flag | off by default | no | boolean | status only |
| ClamAV scanner | `documents/file_security.py` | none (provider selection) | `null` by default | not run | none | status and manual daemon check |
Not integrations in the sense of this wave: RAGAS (opt-in offline evaluation), public company-page research (SSRF-guarded fetch, no credentials; governed in W9.x), billing (does not exist), web-search providers (none).

## 4. Classification
Computed per integration from runtime state: `runtime_active`, `configured_inactive`, `supported_unconfigured`, `code_present_not_validated` (Google OIDC, always), `development_only` (the fake scanner). Supported never means connected, configured never means healthy.

## 5. Canonical registry
`src/integrations.py` `REGISTRY`: nine code-defined integrations, each with code, name, category, adapter, credential slots (environment variable NAMES only), allowlisted settings, optional enabling flag, whether a manual test exists, and a truthful validation note. Admin cannot create an integration, provider name, endpoint or secret field.

## 6. Categories
Only those backed by code: AI/model, labour-market data, authentication, email/communications, rate limiting, observability, file security. No billing category.

## 7. SecretStore design
`src/secret_store.py`: `is_configured`, `source`, `supports_write`, `set` (only where supported), and `get_for_runtime` (returns a `SecretStr`; the only value read path, used by adapter probes and nothing administrative). There is no `get_for_admin`, `reveal` or mask. The evaluator fails if any admin route, schema, provider status or Command Center code references `get_for_runtime`.

## 8. Environment adapter
`EnvironmentSecretStore` reads exactly what the runtime reads (secrets file, then environment): `supports_write=False`, `set` raises `SecretStoreReadOnly`, the process environment is never mutated and `.env` is never written. The Admin UI says "Managed outside Ask4Mo (set NAME in the deployment environment)" and offers no rotate, replace, delete or reveal.

## 9. Writable-adapter decision
No secure writable store exists in this architecture, and none was invented (no plaintext file or database storage). Only the interface and a clearly labelled test adapter (`InMemorySecretStore`, never constructed by the app) exist. The credential-replacement route is implemented and fully tested against that adapter, requires the distinct permission `platform.integrations.secret.rotate` (held by no preset today), and returns 409 for the environment store.

## 10. Secret non-retrievability
Inventory and detail return only `configured`, `source` and `writable` per slot; tests set sentinel secrets for every slot and assert no value, prefix, suffix or mask (`...`) appears anywhere in any integration response. Credential paths found that return a value to an administrator: 0. Paths remaining: 0.

## 11. Configuration persistence decision
All integration configuration is environment- or code-owned, so nothing about configuration is persisted. The one durable need is the result of an explicit manual test, which must survive restarts and be shared across processes. Secrets are stored nowhere in the database, audit, logs or frontend storage.

## 12. Migration decision
One additive migration, `0017_integrations`: table `integration_states` holding only the last manual-test timestamp, outcome, bounded category, latency and who ran it (CHECK-constrained, FK `SET NULL`). No secret, URL, credential identifier or response column. Tested fresh, from 0016, constraints, downgrade and round trip.

## 13. Safe configuration schemas
Responses are explicit allowlist models (`extra="forbid"`). Settings are shown only as members of a code-defined vocabulary (for example provider = console/brevo/memory); any other environment value displays as "other" and is never echoed.

## 14. SSRF boundary
There is no user-controlled URL anywhere: no endpoint field, no create route, no URL in any request body or path. The only probe destination is the adapter constant `https://openrouter.ai/api/v1/auth/key`; the scanner probe contacts the environment-configured daemon. Tests post hostile codes (localhost, RFC1918 and link-local addresses) and get 404, and assert the registry has no endpoint-like setting.

## 15. Status model
Three separate dimensions: configuration (`unconfigured`, `partially_configured`, `configured`), runtime (environment-owned on/off or not applicable, never toggleable here) and health (`not_tested`, `healthy` only after a recorded successful manual test, `unhealthy` after a failed one).

## 16. Manual connection testing
`POST /admin/integrations/{code}/test` (`platform.integrations.manage`) for OpenRouter (key-information endpoint: no model run, no usage cost) and ClamAV (daemon answers; no file scanned). Explicit action only; 5 s timeout; redirects not followed; no retry; no polling; no page-load call. Other integrations return 409 with the reason. The result row and its audit event are written in one transaction (an audit failure rolls the result back).

## 17. Health and error redaction
Any probe outcome, including an exception whose text may contain a credential, is reduced to a bounded category (`ok`, `unauthorized`, `timeout`, `unavailable`, `configuration_error`, `rate_limited`, `unknown`); exception text, response bodies and headers are discarded. Verified with sentinel keys embedded in exception messages and mock response bodies. The global 422 handler no longer echoes the submitted `input`, so a mistyped credential cannot appear in a validation error.

## 18. Credential validation semantics
Three levels are kept apart: configured (a value exists), structurally accepted (8 to 4096 characters, no whitespace; this is all the replace route checks) and connection-tested (a provider probe succeeded). The UI never says "valid".

## 19. Runtime enable/disable boundary
No integration is dynamically toggleable: every enabling flag is environment-owned. There is no enable or disable route (the evaluator checks), the UI shows the runtime state read-only and states that changes need a deployment or restart. `.env` and the process environment are never touched.

## 20. Google OIDC status
Classified `code_present_not_validated` even when configured and flagged: "Backend support present; end-to-end sign-in is not validated and is not wired into the candidate sign-in page." No probe, never enabled by Admin.

## 21. Redis status
Shown as supported; with a URL set but the shared store not active it reads "Configured, not in use" and "distributed limiting is NOT LIVE". It reads the actual runtime (`shared_store_active`), not the configuration.

## 22. Email status
Brevo is "in use" only when selected and keyed; the note states live delivery is not validated and that support ticket replies are never emailed. No probe (a real test would send mail).

## 23. AI/model provider boundary
Connection and configuration only. No model lifecycle, prompt management, activation workflow or approvals (W10.7).

## 24. Labour-market provider boundary
Adzuna status only; no probe because calls consume quota. No P10C work.

## 25. Credential-replacement audit semantics
The store and the audit database are different systems, so no atomicity is claimed. Order: audit `admin.credential_replacement_requested` (fail closed: if it cannot be recorded, nothing is written and the response is 503), attempt the write, then record `..._succeeded` or `..._failed` (best effort, logged without values). The body is parsed manually so a value is never echoed; store errors (which may embed the value) are discarded (502). No rollback or versioning is claimed. Environment credentials have no replace action (409).

## 26. Admin list and detail
`/admin/integrations` (inventory table: support state, credentials, health, last tested) and `/admin/integrations/[code]` (overview, credential slots with source and management note, settings and runtime, connection test, recent management events). English only.

## 27. Permissions
Existing canonical permissions only (registry stays 43): `platform.integrations.read` (list, detail), `platform.integrations.manage` (manual test; now in `platform_admin`; `operations_admin` already held it), `platform.integrations.secret.rotate` (credential replacement; held by no preset, so the route is unreachable in production until a writable store and step-up exist). Candidate, billing, knowledge, support and security presets are denied (tested).

## 28. Command Center
With `integrations.read`: counts of supported, configured, not-yet-tested and last-test-failed integrations. Nothing is inferred healthy; no secret names or fragments.

## 29. No background monitoring
No scheduler, poller, worker, queue or recurring probe; the evaluator scans for them. Scheduled health checks can come with W10.9 jobs.

## 30. Security tests
Secret-leak (list, detail, every slot, prefix/suffix/mask), environment replace refused, write-only round trip, audit without value, exception and store-error redaction, 422 without echo, runtime-read confinement, no admin schema field for a value or URL, no endpoint input, hostile path codes, no network on list/detail/Command Center, persisted state has no secret column.

## 31. Backend tests
**2720 passed, 3 skipped, 0 failed, 0 errors** (baseline 2689/3; the 3 skips are the unchanged live Adzuna, Streamlit-context render and RAGAS tests). New `tests/test_integrations_w10_6.py` (31). Earlier guards updated for head `0017`. `ruff check .` clean.

## 32. Frontend tests
646 unit tests in 80 files (inventory states, configured is not healthy, healthy only on a recorded test, environment-managed credential UI, manual test on request only, unsupported test, read-only role, write-only form with cleared input, no value rendering, no storage or role-name logic). Typecheck, lint, build and scanner (0 offenders) clean.

## 33. Playwright
**207 passed** (206 baseline plus the integrations journey), serial, no retries or timeout changes; providers mocked, no real call.

## 34. Evaluators
**32 of 32** pass including the new `scripts/eval_admin_integrations.py` (25 checks). `eval_admin_design` and `eval_admin_foundation` were updated for Integrations as an operational destination and route.

## 35. Manual QA
Freshly migrated database (head `0017_integrations`) with fake sentinel credentials in the environment: the inventory classified the nine integrations from real state (Google "Code present, not validated", Redis "Configured, not in use"); responses contained no sentinel; the OpenRouter detail said "Managed outside Ask4Mo" with no value or action; a manual ClamAV check (no scanner selected) recorded `configuration_error` and an audit row without values; an unsupported test returned 409; Command Center counted the result. The OpenRouter probe was deliberately not run (it would make a live call). Note: in this development machine the secrets file supplies the OpenRouter key, and the page correctly reported source "secrets file".

## 36. Performance
First Load JS: `/admin/integrations` 114 kB, `/admin/integrations/[code]` 117 kB, `/admin` 115 kB, shared 103 kB (unchanged). No provider code in client bundles; one list request or one detail request per page; the test request only on click.

## 37. Dependencies
None (`httpx` was already a dependency).

## 38. Alembic head
`0017_integrations` (single head).

## 39. Open items
SEC-W10-04 (W10.10), SEC-W10-05 (W10.11), PRIV-W9-01 and PRIV-W9-02 (W10.10) remain OPEN.

## 40. W10.9 handoff
W10.9 can build on the registry, adapters and probe abstraction, `SecretStore`, the safe `integration_states` result record and the permissions/audit, to schedule safe health checks as jobs without redesigning configuration. It must keep probes adapter-defined and bounded and keep the audit-with-state transaction pattern.

## 41. External calls
0 paid or live provider calls.
