# W12.4B - Secure provider and secret administration

**Status: IMPLEMENTED and qualified (deterministic, offline, 0 paid or live provider calls).** W12.4A is complete and merged; this wave changes provider credentials only. Billing semantics, the email workflow, speech, candidate entitlements, the Knowledge architecture and the 43-permission registry are unchanged.

## 1. Architecture before and after
| | Before (W10.6) | After (W12.4B) |
|---|---|---|
| Store | `EnvironmentSecretStore`: read-only. Credential replacement existed as a route but always returned "managed outside Ask4Mo". | Default is still the environment store. With `SECRET_STORE_BACKEND=encrypted_database` the store is `LayeredSecretStore`: **managed (encrypted) credential, then environment fallback, then not configured**. |
| Writing | Impossible. | Admin configures, replaces and removes a credential for a code-defined (integration, slot). |
| Runtime | Consumers read the environment (several directly through `os.environ`). | Every current secret consumer reads through `src.core.secrets`, which asks the managed resolver first and then the environment. |
| Gate | `platform.integrations.secret.rotate` | the same permission **plus a fresh password step-up of the current session**; the audit event is written in the same database transaction as the change. |

The abstraction was extended, not duplicated: `src/secret_store.py` keeps the `SecretStore` protocol (`is_configured`, `source`, `get_for_runtime`, `set`) and adds `remove`, `write_state` and `managed_meta` (metadata only). There is still no method that returns a value to an administrator.

## 2. Integration inventory (repository truth: 9 integrations, 11 secret slots)
| Code | Purpose | Runtime consumer | Secret slots | Non-secret settings (environment-managed) | Managed override reaches the consumer | Admin test | Test makes an external call |
|---|---|---|---|---|---|---|---|
| `openrouter` | Language models for Mo and Practice | `src/config.py`, `src/core/config.py`, `src/copilot/config.py` (config cached for the app lifetime) | `api_key` | none | after API and worker restart | yes | yes: one key-information request to OpenRouter, only when an operator starts it |
| `openai_embeddings` | Optional embedding provider | `src/copilot/config.py` (cached) | `api_key` | provider | after restart | no | no |
| `realtime_voice` | Optional live voice | `src/voice/realtime.py` (read per session) | `api_key` | provider, enabled flag | next use | no | no |
| `adzuna` | Current-market job data | `src/copilot/knowledge/providers/adzuna.py` (read per call) | `app_id`, `app_key` | none | next use | no | no (quota-gated) |
| `google_oidc` | Google sign-in (not validated live) | `src/application/oidc.py`, `get_oidc_provider` (per request) | `client_id`, `client_secret` | enabled flag | next use | no | no |
| `email_brevo` | Account emails | `src/mail/sender.py`, `build_email_sender` (shared for the app lifetime) | `api_key` | provider, sender | after restart | no | no (a test would send mail) |
| `redis_rate_limit` | Shared rate limiting | `src/api/rate_limit.py`, process-global limiter | `url` | backend | after restart | no | no |
| `langfuse` | Optional observability | `src/observability`, sink built once | `public_key`, `secret_key` | enabled flag, host | after restart | no | no |
| `malware_scanner` | ClamAV upload scanning | `src/documents/file_security.py` | none | `FILE_SCAN_PROVIDER` (`clamav` or `fake`) | n/a | yes | local daemon ping only, no file scanned |

"Next use" means the consumer reads the credential when it needs it, bounded by the store's 5 second cache. "After restart" means the consumer builds its client once per process, so the API and worker must restart; the Admin page says which applies to each slot and **never claims immediate rotation where a restart is needed**. Making the cached OpenRouter configuration refresh in place is a candidate for W12.4F.

## 3. Encrypted store and encryption model
- `EncryptedDatabaseSecretStore` keeps one row per (integration, slot) in `managed_secrets`: **AES-256-GCM** ciphertext, a 12-byte random nonce generated per write, a short key id, a revision and timestamps. It uses `cryptography` `AESGCM`; there is no custom cryptography.
- The (integration, slot) is bound to the ciphertext as authenticated associated data, so a ciphertext moved to another slot does not decrypt.
- The row holds **no plaintext, mask, prefix, suffix, fingerprint or history**. Rotation replaces the row: old ciphertext is not retained and credential rollback is not offered.
- A tampered ciphertext, a wrong key or a missing key never raises into a page or runtime call: the managed value reads as unreadable, the runtime falls back to the environment value if one exists, and Admin shows that the managed credential cannot be read.

## 4. Master key bootstrap (intentional)
The encryption key is infrastructure bootstrap configuration: `SECRET_STORE_MASTER_KEY` is standard base64 of **exactly 32 random bytes**, validated strictly (no password derivation, no padding repair). It cannot live in the database it encrypts, so it stays **deployment-managed**: no Admin control, no API response and no audit field ever contains it. Provider credentials become Admin-managed; the master key does not. If the encrypted backend is selected and the key is missing or malformed, secret writes fail with a bounded "secure credential store unavailable" state, nothing is stored in any form, and **production and staging refuse to start** (`env_validation`).

Generate a key (for example): `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`. Never commit it.

## 5. Resolution precedence and no backfill
1. Admin-managed encrypted credential (when present and readable)
2. environment or secrets-file credential
3. not configured

Environment secrets are **never** copied into the database. Removing a managed credential deletes only that row; the environment value, if any, is used again, otherwise the credential is not configured. Selecting the default `environment` backend ignores any managed rows and touches no database path.

## 6. Authorization, step-up, approval
- **No 44th permission.** The registry stays exactly 43. `platform.integrations.secret.rotate` is held only by `platform_admin`; `operations_admin` holds `integrations.read` and `integrations.manage` but not `secret.rotate`, so it may inspect integrations and run permitted non-secret actions but can neither configure, rotate nor remove a credential. No specialist preset changed. That boundary is recorded as a role-scope finding, not silently changed.
- **Step-up:** the existing `StepUpService` (password re-authentication bound to this server-side session, 5 minutes, rate limited, fails closed for an account without a password credential such as OIDC-only). Configure, replace and remove all require it; `platform_admin` cannot bypass it. The UI reuses the existing step-up dialog and retries the same write.
- **Two-person approval is not required** for secret rotation (the owner-approved scope is permission, step-up and audit). Role changes keep their existing two-person rule.

## 7. Audit
Bounded metadata only: integration code, slot, action (`created`, `rotated`, `removed`), result, request id and actor. Never a value, ciphertext, nonce, key, fingerprint or mask. For the encrypted store the success event is written in **the same transaction** as the change, so a failed audit stores nothing; failure events (stale revision, store unavailable, read-only) are written after the fact. Events: `admin.credential_replacement_succeeded` (carries the action), `admin.credential_replacement_failed`, `admin.credential_removed`.

## 8. API contract
All under `/api/v1/admin/integrations/{code}` and permissioned; there is no PUT, PATCH, DELETE, reveal, export or "get value" route.
- `GET` and `GET /{code}`: metadata per slot: `configured`, `source_kind` (`managed`, `environment`, `none`), `managed`, `managed_readable`, `revision`, `last_rotated_at`, `environment_fallback`, `required`, bounds, `applies`; and the store view `state` (`writable`, `read_only`, `unavailable`) with a bounded `reason`.
- `POST /credentials/{slot}` body `{value, expected_revision?}`: `value` is `writeOnly`, `format: password` in OpenAPI; the body is parsed by hand so no validation error can echo it. Responses: 200 metadata (`action`, `revision`), 403 `step_up_required`, 404 unknown integration or slot, 409 stale revision or read-only store, 422 bounded shape error, 503 store unavailable (fixed copy).
- `POST /credentials/{slot}/remove` body `{confirm: true, expected_revision?}`: deletes the managed row only.
- `POST /test` is unchanged: saving a credential never calls the provider, so the state after a save is "configured, not tested".

## 9. UI contract (`/admin/integrations`, `/admin/integrations/{code}`)
No new destination. Each slot shows its source (Managed secure store, Environment, Not configured), last change time, whether a new value applies on next use or after restart, and, with `secret.rotate`, **Configure credential**, **Replace credential** and **Remove managed credential**. The input is a blank password field that is never pre-filled and is cleared after every attempt; the value is held in an uncontrolled input, never in state, the URL, `localStorage` or `sessionStorage`. The store state is stated plainly (writable, environment read-only, or unavailable with the reason). Configured is never shown as healthy.

## 10. ClamAV and the file scanner
Unchanged and fail-closed: without a configured scanner, governed Knowledge uploads fail with `scan_unavailable`. Admin reports the scanner as configured or not and its manual test as not run, healthy or failed. The `fake` scanner is **not** selectable from Admin and is not production-capable; `FILE_SCAN_PROVIDER` stays a non-secret **environment-managed** setting. No ClamAV daemon was deployed. Scanner endpoint and provider selection is recorded for W12.4F.

## 11. Threat model (summary)
| Threat | Control |
|---|---|
| Database dump | only AES-256-GCM ciphertext; the key is not in the database |
| Admin or API reads a secret | no read path exists; the only value read is `get_for_runtime`, confined to the store and adapter probes (guarded by `eval_admin_integrations`) |
| Secret in a response, validation error, audit row, log or exception | hand-parsed body, bounded fixed messages, sentinel leakage tests across responses, audit rows and captured logs |
| Stolen Admin session | fresh password step-up per 5-minute window, bound to the session |
| Lost update | `expected_revision` on replace and remove |
| Ciphertext swap between slots | slot bound as associated data |
| Arbitrary secret or provider | only code-defined (integration, slot) names resolve |
| Weak key | exactly 32 random bytes, strict base64; no derivation |

## 12. Limitations and what is not implemented
- Rotation of OpenRouter, embeddings, Brevo, Redis and Langfuse takes effect only after the API and worker restart (their clients are built once per process). Realtime voice, Adzuna and Google sign-in read at use.
- Cross-process convergence of a rotation is bounded by the 5 second cache.
- The master key is deployment-managed (no rotation of the key itself, no key-version migration tool yet; the `key_id` column is recorded for that).
- Non-secret provider settings (provider selection, sender identity, scanner provider, flags) remain environment-managed.
- Not implemented: email operations (W12.4C), live billing (W12.4D), Whisper or Pocket TTS (W12.4E), configuration completeness (W12.4F), a generic environment or secret editor, break-glass, impersonation, secret export, credential rollback, MFA.
- The step-up is password re-authentication, not MFA; an OIDC-only administrator cannot step up and so cannot write credentials.
- The PostgreSQL path for `managed_secrets` is migration-tested on SQLite only.

## 13. Operator validation (normal developer environment, 2026-10-14)
Measured after the isolated tests were green. No external provider was contacted and no real credential was used.
- **Migration through the normal path.** The developer database (correct lineage since W12.4A) was backed up with an SQLite online backup outside the repository, then `alembic upgrade head` took it from `0025_security_audit_incidents` to `0026_managed_secrets` (no stamp, no reconciliation). Schema objects 226 to 228 (the table and its unique index), `integrity_check` ok, 11 accounts and 46 interviews unchanged.
- **Flow.** The API ran with `SECRET_STORE_BACKEND=encrypted_database` and a development-only master key generated with secure randomness, held in a mode-600 file outside the repository for the session and deleted afterwards (never printed, never committed). A temporary platform-admin account stepped up with its password, configured dummy Adzuna credentials, and a separate fresh process (constructing the real Adzuna credential reader) saw the managed values while the environment held a different `ADZUNA_APP_ID`. Rotation to a second dummy (revision 2) made the first stop resolving; a stale-revision write returned 409; removal restored the environment value for `app_id` and the existing developer environment value for `app_key`. Responses carried metadata only and the health stayed "not tested" after a save.
- **Leakage.** No dummy value appeared in any API response, in the audit rows (`admin.credential_replacement_succeeded`, `admin.credential_removed`, one expected `admin.credential_replacement_failed` for the stale write) or in the API log. The dummy managed rows were removed (0 left) and the temporary account was deleted through the normal account-deletion route (accounts back to 11).
- **Explained database change (snapshot, not invariant).** At rest after validation the developer database SHA-1 is `8249073160a99c912a971cec4fc30da1fb981f33` (revision 0026, 228 objects). The difference from the post-migration snapshot `06cb378224c991ae7be1f600745e418c72aec5ce` is legitimate operation: audit events, a temporary account's session and deletion records. Chroma `85fc95aa...`, checkpoint `b56d0c39...`, research cache `25264b17...` and `evaluations/` `67259aba...` are unchanged.
- **Not covered live:** a browser walk-through against the live API (the UI flow is proven with deterministic Playwright mocks) and any live provider health.

## 14. Handoff
W12.4C (Email and Identity Operations) can use the new store for the Brevo and Google credentials and add the operational workflow; W12.4F should absorb the remaining environment-managed non-secret settings and the in-place refresh of cached provider configuration.
