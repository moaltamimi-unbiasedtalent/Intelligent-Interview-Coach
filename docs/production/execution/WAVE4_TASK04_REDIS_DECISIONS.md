# Wave 4 Task 04 — Redis shared limiting and outage decisions

24 October 2026. Baseline PR #269 merged at `5e524ca893e71a59648f4fb48f9d193b3c6f77a1`. Main CI [40126702547](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40126702547), immutable images [40126702570](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40126702570), migration image [40126702582](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40126702582) and durable admission [40126702591](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40126702591) all passed. Browser E2E is PR/on-demand, not a main-push workflow; PR #269's browser evidence remains its own SHA-bound historical result.

**Preparation and disposable qualification only. No staging activation, provisioning, registry publication, real database migration, paid call, live email, language activation or gate acceptance.** [Pre-change audit and all 37 bucket policies](WAVE4_TASK04_REDIS_AUDIT.md). Final candidate CI and image provenance are recorded in the focused PR.

## Implemented behavior

The existing adapter and Lua sliding window are retained. Redis server time now defines the window, preventing client clock skew from trimming another instance's events. Each event has a unique random member. Hosted keys contain a code-defined bucket plus HMAC-SHA256 of the bucket/key pair, using one shared independent secret; no raw email, IP or user ID is written into the Redis key. All API replicas must use the same namespace and key secret.

Redis-py **8.1.0** is an optional pinned extra installed in the existing non-root API image. Connection and command timeouts are 1 second, connections are capped at 16 per process, protocol is explicitly RESP2 and automatic retries are disabled. Ambiguous network failures are not retried inside an admission. A subsequent request may reconnect; an ambiguous successful write can conservatively consume a slot. Application configuration uses the existing managed/Streamlit/environment secret resolver for REDIS_URL and RATE_LIMIT_KEY_SECRET, with an optional read-only REDIS_PASSWORD_FILE. Runtime secrets never enter image layers, release manifests or copied plan assets. In required-shared mode, a managed/Streamlit value that shadows a different explicit deployment URL/key secret is refused; clear the stale source or coordinate one reviewed value before activation. This prevents the reviewed profile and actual client silently selecting different stores.

Hosted shared selection (including an implicit REDIS_URL) rejects absent dependencies, malformed/query-overridden URLs, missing credentials, missing isolated namespace or missing >=32-character key secret. It requires authenticated TLS for a managed endpoint; plaintext is allowed only for the explicitly selected private `redis` service. Construction errors cannot silently select memory in hosted/required operation. Development's ordinary single-process default and explicit development fallback remain available and honestly reported. The in-memory fallback now caps stored identities without evicting live counters to create fresh allowances.

**Every existing bucket remains `local`.** No limit, endpoint coverage, failure policy, billing gate, AI observe-mode constant, entitlement, language record or PostgreSQL admission implementation is activated/changed. `deny` is qualified through synthetic policy instances; it returns HTTP 503 with a bounded Retry-After on store failure, while an actual exceeded request ceiling is HTTP 429. Real auth tests found that the central error handler discarded Retry-After; only numeric bounded retry values and the code-defined readiness state header are now forwarded. Arbitrary exception headers/detail remain hidden. Allowed CORS origins can read Retry-After; the browser never shortens a server minimum delay to its automatic-wait ceiling. A longer hint surfaces the existing error without an early retry; writes remain non-retryable. Late limiter-configuration refusals are safe HTTP 503, without exposing configuration detail.

## Selectable topology, pending OD-HOSTED

| Choice | Requirements and trade-off |
|---|---|
| Internal Redis | Official `redis:8.2.9-alpine@sha256:5f2e6a105b2a8cc721911d5d29aadb032c25fe55b43e829e3d03413753ff47c2`; isolated internal network, no published port, UID 999/GID 1000, read-only root, dropped capabilities/no-new-privileges, read-only credential/startup mounts, ephemeral tmpfs. Single failure domain; no HA claim. |
| Managed Redis | Private, authenticated `rediss` endpoint compatible with the existing standalone Redis client, Lua and TIME. Same approved region as the API/data, private routing/firewall, certificate validation, provider residency/privacy/retention review, least-privilege ACL and measured failover required. Cluster/Sentinel/multi-region operation is not qualified by this task. |

Recommend a managed private endpoint when approved availability requirements justify it; the internal option permits controlled isolated staging without inventing a provider decision. The owner still chooses topology, region, provider, cost, operator, secret delivery and explicit staging authorization. The Redis 8.2 extended-support line is [maintained through September 2030](https://redis.io/docs/latest/operate/oss_and_stack/install/version-mgmt/); the pinned 8.2.9 [security release](https://redis.io/docs/latest/operate/oss_and_stack/stack-with-enterprise/release-notes/redisce/redisos-8.2-release-notes/) was verified against the official image index. Pins need review for security updates; no vulnerability-free claim is made.

The internal application ACL permits only PING, EVAL and the script's TIME/sorted-set/expiry operations within the selected namespace. No SCAN, FLUSH, CONFIG, ACL administration, persistence or cross-namespace access. Health uses authenticated PING; API readiness exercises the actual Lua path on one short-lived synthetic health key without charging a product bucket. OOM uses `noeviction`: it becomes an observed store failure, not silent eviction of active counters.

## Immutable plan integration (no execution)

Use the existing reviewed release builder/verify commands first. Supply a trusted manifest anchor and expected SHA. Examples below create files only; they do not start services.

```sh
python scripts/release_images.py prepare --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-hash> \
  --state <fresh-drained-state.json> --mode promote --env-file <absolute-private-env> \
  --redis-topology internal --redis-namespace ask4mo:rl:staging:v2: \
  --redis-password-file <absolute-operator-password-file> --out <NEW-plan-directory>
# Managed option: --redis-topology managed --redis-namespace ask4mo:rl:staging:v2:
# Omit --redis-password-file; deliver an authenticated rediss URL at runtime.
python scripts/release_images.py check-compose --manifest <bundle>/release.json \
  --expected-sha <reviewed-SHA> --manifest-sha256 <trusted-hash> \
  --state <same-fresh-state.json> --mode promote --env-file <absolute-private-env> \
  --profile <plan>/compose.yml
```

The generator pins API/worker to the same explicit backend, required-shared flag and namespace, preserves their exact shared application image, private volume identities and successful one-shot migration dependency, and validates the Redis network/security/health/credential bindings. It copies only committed, hashed startup code; no credential contents. Managed profiles add no local Redis service. No unreviewed Compose overlay is needed. API/worker/migrate remain one image; web stays bound to its manifest. The profile refuses a release without the pinned client. `--mode rollback` still removes the migration service entirely and refuses incompatible schema, unsettled usage or stale/undrained state. No SQL write, downgrade, restore, force-unlock or Redis bulk-clear operation was added.

Internal credentials must be >=32 URL-safe characters, in an operator-private directory and readable by the container UIDs through the approved read-only secret delivery. The API UID is 10001; Redis UID is 999. File-backed Compose secrets do not guarantee host ownership remapping: qualify actual host permissions before activation. Keep the HMAC secret independent of the Redis password and deliver it via the private runtime environment/secret store. Never paste secrets into command arguments, manifests, issue/PR bodies or logs. Secret rotation requires a drained coordinated release.

Pre-Task-04 images lack the pinned client; they are not a qualified shared-Redis rollback target. Use a separately reviewed compatible image or forward-fix. Do not claim that an older image can enforce the new shared policy merely because its database schema matches.

## Outage policy and readiness (H-REDIS-POLICY remains OPEN)

The audit contains the complete per-bucket numeric matrix. Authentication/registration/recovery, privileged security actions, AI request buckets and webhook protection are recommended for `deny`; support/privacy/legal availability needs owner review as well. The recommendation is not approval and no existing bucket was switched.

- **local:** keeps the current bounded per-process requests available; loses the global ceiling. N replicas can admit N local ceilings, plus further shared admissions after recovery. Local histories are not merged into Redis. This is not a financial guarantee.
- **deny:** refuses a protected request during a store failure and avoids local admissions, at the cost of availability. HTTP 503/Retry-After distinguishes unavailable protection from HTTP 429 for an exceeded ceiling. Existing Practice/Career request limits are observe-only; their separate owner-approved activation and monetary budget enforcement belong to Task 05.
- **RATE_LIMIT_SHARED_REQUIRED=true:** an explicit shared deployment also gates readiness on observed distributed enforcement. A degraded replica is removed from rotation if the balancer honors readiness, even though already-routed requests still apply their bucket policy. The generated optional profiles select this conservative readiness contract; approval/activation remains pending. The ordinary dev/single-process default is unchanged.

Status distinguishes configured/unverified, reachable shared, unreachable, degraded local, fail-closed refusals and recovered shared enforcement. Admin sees only bounded status and per-process counters. Successful readiness includes the state in dependencies; a failed probe preserves the existing safe error envelope and conveys only an allowlisted X-Rate-Limit-State header. A shared-store construction alone never claims active enforcement. Probes are throttled to two seconds per process; readiness is an observation, not proof of an uninterrupted global guarantee or hosted qualification.

## Monitoring and restart consequences

Existing application logging emits bounded outage/recovery transitions; Admin/readiness expose safe observations. No new external telemetry/paging service is activated. Monitor every API replica; counters are process-local observations, reset on restart and are not billing or audit totals. Establish named on-call ownership and authorize alert routing before hosted use.

Proposed thresholds: warn immediately on any degraded/unreachable probe; page for >=30 seconds of lost shared enforcement, any fail-closed refusal, or any positive local-fallback delta in a required-shared deployment. Alert on namespace/config drift and Redis memory pressure/noeviction errors before exhaustion. Verify alert, outage and recovery timing on the actual host; these are proposed thresholds, not owner-approved SLOs.

Internal Redis intentionally persists no candidate data or counter snapshots. Keys expire at the bucket window plus at most one second; the longest shipped window is 3,600 seconds. Restart/failover/secret or namespace rotation may reset allowances. First rollout changes key format: drain all old writers and wait the longest window, or obtain explicit owner acceptance of a counter reset. Never overlap old/new key formats or different secrets/namespaces while claiming a global ceiling. No automatic counter migration or database change is performed. PostgreSQL durable run admission and real usage accounting remain authoritative through settlement.

## Evidence and remaining work

The real suite owns disposable Redis containers, synthetic credentials, dedicated networks and isolated SQL test fixtures. Host clients use a loopback-only test mapping; a separate unmodified production startup test has an internal network and no published port. A test-only operator ACL supports TTL inspection/legacy cleanup; the application identity retains the production restriction and is tested against forbidden commands. Local Colima requires fixture paths shared with its VM; CI uses its own native temporary filesystem. Neither is staging deployment.

Actual local evidence: **404 focused checks passed; 16 disposable Redis checks passed, including the exact private Compose healthcheck and 3 nested legacy Redis tests; 13 real-image checks passed with 3 nested disposable PostgreSQL migration tests.** [Measured artifact and local image IDs](evidence/WAVE4_TASK04_REDIS.json). Candidate images were built from `f755665780e6c1b57f6ab3a731cffdea7ce18019`; subsequent status/tool/test/doc refinements have a later commit and are built again by final-head CI. Do not attribute these local IDs to that later head. The direct release CLI prepared and checked an internal profile with `executed: false`. The final retry follow-up passed 27 backend and 36 frontend tests, type checking/linting, and repeated all 16 real Redis checks after proving browser-visible headers and no early automatic retry. Required CI includes full backend/frontend, Browser E2E, migration-image, durable admission, immutable image/topology and mandatory real-Redis workflows. The three original 05D real Redis tests execute inside the owned disposable suite, rather than silently skipping. No hosted provider, email, AI or real candidate data is needed.

R1.0 remains **40/45 engineering packages integrated**, with 00A/00B/07B/07C/08A open/incomplete. Only the existing PG-11 acceptance remains; PG-02/06/09 and every language gate are not accepted by these tests. OD-HOSTED and H-REDIS-POLICY remain OPEN. Hosted credentials/network/region/ACL/TLS/HA/monitoring and alert drills require authorization and real host evidence.

Next, after this focused PR is reviewed, merged and main is green: **Task 05 AI budget enforcement and cost-governor qualification**, with fresh owner-approved ceilings/pricing/limits/marker and disposable refusal/accounting tests. No paid evaluation is authorized. Encrypted backup/restore/rollback is a separate subsequent milestone; its custody, retention, off-host destination and current-head restore-seeder gaps remain open. Scanner, embeddings/source licensing, SSE/proxy behavior, language/human review and 08A go/no-go remain release dependencies.
