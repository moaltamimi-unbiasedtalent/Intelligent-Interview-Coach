# Wave 4 Task 04 — baseline Redis audit

Recorded before implementation on 24 October 2026 against merged PR #269, main `5e524ca893e71a59648f4fb48f9d193b3c6f77a1`. Feature branch: `feat/staging-redis-outage-controls`. Original 45 worktrees, 49 protected file hashes, private databases/environments and unpublished artwork are preserved. This records code findings, not hosted qualification or owner approval.

## Findings before implementation

- All 37 registered buckets select the same Redis adapter when configured; otherwise all are process-local. Every existing bucket explicitly defaults to `local`; none uses `deny`. Defaults must remain unchanged pending H-REDIS-POLICY.
- Lua trim/count/add is atomic across replicas, but uses each client wall clock. Clock skew can trim another replica's events prematurely. Redis keys currently include raw IP addresses and user IDs; email-derived keys are hashed but unsalted.
- Missing Redis URL/package or client-construction failure selects in-memory. Hosted validation catches explicit backend requests missing URL/package, but implicit URL selection and runtime construction errors are not consistently guarded.
- The Redis dependency is absent from the API image. Compose has no Redis service; its template selects in-memory. No real Redis CI is mandatory. Existing real-Redis tests skip when absent/unreachable; fake-store tests are useful unit evidence only.
- `shared_store_active` is set at client construction, before any server command. Runtime degraded state is separate and the Admin summary can incorrectly retain the active claim. `/ready` does not report Redis. Logs are bounded, but no explicit recovered/fail-closed/degraded-local lifecycle is available.
- HTTP `enforce` returns 429 with Retry-After for rate refusals. Auth applies account/IP limits before account lookup; registration and recovery anti-enumeration contracts remain unchanged. The optional `deny` policy returns a refused result, but no current bucket selects it.
- Practice/Career `ai_protection.admit` records rate observations while `AI_COST_LIMITS_ENFORCED=False`. This is NOT an AI money/token budget and must not be activated by this task. Agent/company guards, uploads, speech and realtime endpoints use their existing enforced request buckets. No provider calls are needed for this task.
- `RealtimeSessionLimiter` is a separate in-memory rate/concurrency guard in `src/voice/realtime.py`; keep this additional guard and disclose its local scope. PostgreSQL durable agent admission from PR #268 is separate and stays authoritative through settlement. Redis must not replace it.

## Endpoint map

Auth: login, registration/invitation attempts, recovery/reset, verification resend, OIDC start and global auth. Cost: agent run/stream, company research, documents/extraction, speech STT/TTS, realtime creation; Practice/Career calls additionally use observe-only operational admission. Support/privacy/legal: ticket create/reply, privacy requests and legal acceptance. Security: step-up, workspace transfer, invitation issue, role request/approval and bulk admin actions. Billing/mail: candidate checkout/status/summary/recovery, signed provider webhooks and self-address email test; their existing authorization/code gates remain intact. Global cost applies through the existing agent/research guards and Practice/Career observation, not every direct speech/upload/realtime call. This task does not silently add new buckets or scope.

## Complete existing bucket policy matrix

All values below are REQUESTS/window, not tokens or currency. `local` means one ceiling per process during store failure; N replicas may admit up to N local ceilings, and recovery can admit further requests because local histories are not merged into Redis. No fail-closed approval is inferred.

| Bucket | Requests | Window seconds | Scope | Actual outage policy |
|---|---:|---:|---|---|
| `auth_login_ip` | 20 | 300 | ip | `local` |
| `auth_login_account` | 8 | 300 | account | `local` |
| `auth_register_ip` | 8 | 3600 | ip | `local` |
| `auth_verify_resend` | 5 | 3600 | account | `local` |
| `auth_verify_resend_cooldown` | 1 | 60 | account | `local` |
| `auth_forgot_ip` | 6 | 3600 | ip | `local` |
| `auth_forgot_account` | 4 | 3600 | account | `local` |
| `auth_reset_ip` | 12 | 3600 | ip | `local` |
| `auth_oidc_start_ip` | 30 | 3600 | ip | `local` |
| `auth_global` | 2000 | 300 | global | `local` |
| `auth_invitation_ip` | 10 | 3600 | ip | `local` |
| `auth_invitation_global` | 400 | 3600 | global | `local` |
| `cost_agent_user` | 60 | 3600 | user | `local` |
| `cost_interview_user` | 120 | 3600 | user | `local` |
| `cost_career_user` | 60 | 3600 | user | `local` |
| `cost_research_user` | 30 | 3600 | user | `local` |
| `cost_upload_user` | 40 | 3600 | user | `local` |
| `cost_realtime_user` | 12 | 3600 | user | `local` |
| `cost_speech_stt_user` | 60 | 3600 | user | `local` |
| `cost_speech_tts_user` | 120 | 3600 | user | `local` |
| `cost_global` | 5000 | 3600 | global | `local` |
| `support_create_user` | 10 | 3600 | user | `local` |
| `support_reply_user` | 60 | 3600 | user | `local` |
| `privacy_request_user` | 5 | 3600 | user | `local` |
| `legal_accept_user` | 30 | 3600 | user | `local` |
| `stepup_user` | 5 | 300 | user | `local` |
| `invitation_issue_user` | 60 | 3600 | user | `local` |
| `admin_bulk_user_actions` | 10 | 3600 | user | `local` |
| `role_request_user` | 20 | 3600 | user | `local` |
| `role_approve_user` | 30 | 3600 | user | `local` |
| `email_test_user` | 3 | 3600 | user | `local` |
| `billing_checkout_user` | 10 | 3600 | user | `local` |
| `billing_status_ip` | 120 | 300 | ip | `local` |
| `billing_webhook_ip` | 600 | 60 | ip | `local` |
| `mail_webhook_ip` | 600 | 60 | ip | `local` |
| `billing_recovery_user` | 20 | 3600 | user | `local` |
| `billing_summary_user` | 120 | 300 | user | `local` |

## Recommendation, pending owner decision

Recommend `deny` for authentication/registration/recovery, privileged/security actions, provider-cost operations and signed webhook protection. Support/privacy/legal availability trade-offs need owner review too. Deny preserves a shared ceiling during outages by refusing work; local keeps bounded per-process availability but loses the global guarantee. Practice/Career observation and AI-budget enforcement require their separate approved activation; do not describe them as spending prevention. OD-HOSTED (topology, region, network, secrets, operator) and H-REDIS-POLICY remain OPEN. PG-02/06/09 and all language gates remain unapproved.

## Follow-up from real HTTP qualification

The limiter's HTTPException carried Retry-After, but the central handler discarded it. Real account/non-account refusal tests exposed this end-to-end gap. The focused repair forwards only bounded numeric retry values and a code-defined readiness state header; arbitrary headers and detail remain hidden. All original bucket values/policies above remain unchanged.

Browser transport follow-up: the allowed CORS response did not expose Retry-After, and the existing GET retry helper shortened long server delays to four seconds. The focused fix exposes only the safe retry hint and surfaces the existing error when a full server delay exceeds the automatic-wait ceiling. Writes remain non-retryable; no origin or bucket policy is broadened.

Production-pool burst follow-up: the initial 16-connection cap used immediate rejection and caused 48 local fallbacks in a synchronized 64-request burst while Redis was healthy. Bounded pool backpressure repairs that introduced defect; a mandatory production-factory burst regression now requires exactly the shared ceiling and zero fallback. Actual store/capacity timeouts still follow the unchanged bucket policy.
