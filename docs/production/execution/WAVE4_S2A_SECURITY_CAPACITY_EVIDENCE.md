# Wave 4 Task 08 — S2-A security, access and capacity evidence

**PROPOSED — REVIEW ONLY.** All 16 S2 acceptance entries remain **OPEN**; execution is **BLOCKED**. This is documentation and evidence preparation, not permission to access an account, provision, configure or deploy.

Review date: **27 October 2026**. Source baseline: **f62310eed0eb10bd68b0d806094f9eea47a0aaff**. Editorial starting point: the owner's supplied “S2-A Security, Access and Capacity Evidence Review” packet; claims were checked against the repository and current main CI. The source attachment is not copied into Git.

## 1. Verified baseline and exact-source evidence

PR #278 merged at this baseline from head a7239ca17b59d53a3c3c4debf8980f87efdc148b. No duplicate S2-A PR was present at baseline inspection. All seven required **main-push** workflows are **VERIFIED** completed SUCCESS on f62310ee:

| Workflow | Run / result |
|---|---|
| Redis shared limiter regression | [40571392315](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392315) — SUCCESS |
| AI budget governor qualification | [40571392242](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392242) — SUCCESS |
| Staging migration image regression | [40571392181](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392181) — SUCCESS |
| Immutable local release regression | [40571392213](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392213) — SUCCESS |
| Encrypted recovery qualification | [40571392182](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392182) — SUCCESS |
| Agent durable admission regression | [40571392225](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392225) — SUCCESS |
| CI | [40571392204](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392204) — SUCCESS |

A main pass is not an exact-head result for this documentation PR; the PR checks must finish independently. No new local test result is inferred here.

**Current-source Task 07 campaign — VERIFIED offline evidence:** downloaded the existing synthetic main artifact from [immutable run40571392213](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40571392213), artifact **12767216418**, `disposable-integration-evidence/summary.json`. Its source_sha is exactly f62310eed0eb10bd68b0d806094f9eea47a0aaff; summary bytes SHA256 **ae10643d10b9cee47a65986b5fcb120238ccd01b95cafd05b103217b2513b750**. Counts are **29 PASS / 0 FAIL / 0 SKIP / 6 NOT RUN**; machine result remains `PARTIAL_EXTERNAL_DEPENDENCIES`. API, worker and migrate share application image **sha256:d577c1f371eece112f16ce35b72f2d2dd6bbe026d1c588cf0aa014483ad3c08f**; matching web image **sha256:5395ecee8536ce402f6f3c42435514117ce984a13e2a65bc1ab306305c00fb8d**. These are local immutable image IDs from that CI source, not registry distribution digests or a hosted release approval.

All six external scenarios stay **NOT RUN**: new hosted-language registration/interviews; positive language interview/career journeys; live AI quality/embeddings; real email/OIDC; hosted TLS/signature freshness; recovery-hold release.

The committed [Task 07 evidence](evidence/WAVE4_TASK07_INTEGRATION.json) and [Task 08 preflight](evidence/WAVE4_TASK08_PREFLIGHT.json) retain their historical b463cf9b / earlier-source results, including failed 27/2/6 attempts. They are not relabeled as f62310ee evidence or rewritten. Task 07 remains **OFFLINE QUALIFIED — MERGED**. No new S2 hosted test or benchmark was performed.

## 2. Exact H01/H02 envelope — no amendment

Authority: [exact owner decision](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md), [owner register](../OWNER_DECISION_REGISTER.md) and [existing 16-entry S2 checklist](WAVE4_S2_SECURITY_ENTRY_CHECKLIST.md). Approval is **FOR S1 DOCUMENTATION ONLY**; overall OD-HOSTED remains **PARTIAL / OPEN**. This task authorizes only the S2-A review document.

| Attribute | Recorded constraint |
|---|---|
| Provider / location | Hetzner Cloud / Nuremberg Germany, nbg1 |
| Intended isolated project | ask4mo-staging-eu; actual project existence NOT VERIFIED |
| Exact VM / disk | One CPX42 x86 Linux, included 320 GB disk; no fallback |
| Published planning shape | 8 shared x86 vCPU / 16 GB advertised RAM; not measured guest capacity or dedicated CPU |
| Network resource scope | One primary IPv4, IPv6, one private network and firewall configuration |
| Operator / tester / operations / billing / shutdown | Mo Al-Tamimi only; no other access, custody or reviewer role inferred |
| Primary app / DB / documents / index / logs / runtime secrets | Germany only; actual contractual and technical compliance NOT VERIFIED |
| Future encrypted independent backups | Germany or France only after separate provider/account/contract/custody/retention/procedure approval; no backup service purchase now |
| Ceiling | EUR150 including applicable VAT and all authorized infrastructure charges |
| Fixed start, inclusive | 2026-10-28 09:00 CET / 2026-10-28T08:00:00Z |
| Fixed expiry, exclusive | 2026-11-27 09:00 CET / 2026-11-27T08:00:00Z |
| Duration | 30 calendar days / 720 hours; no shift, scaling, renewal or automatic extension |

No extra instance, volume, snapshot, cloud backup, managed database, external paid secret/monitoring service or registry is authorized. No paid AI/embeddings/OCR, real candidate data, transactional email/OIDC, public beta, live billing, unqualified language, deployment, migration, key generation or recovery-hold release. An unused portion of EUR150 is not permission to add a service. The ceiling is an owner constraint, not demonstrated provider-native hard enforcement.

## 3. Account and location verification matrix

Only already available or voluntarily owner-supplied **redacted, noncredential evidence** may be reviewed. None was supplied with the editorial packet that independently establishes the account facts below. Naming a project/operator in an approval is not an observation of their provider configuration.

| Fact to verify | Finding | Acceptable additional evidence / review |
|---|---|---|
| Account/project existence and identifier | NOT VERIFIED | Dated redacted project/account ownership record, provider project reference retained privately |
| Operator MFA | NOT VERIFIED | Dated redacted security-setting attestation; no recovery codes |
| IAM/least privilege and billing access | NOT VERIFIED | Mo-only role/permission and billing-visibility inventory, privileged actions/revocation plan |
| Recovery ownership, access revocation, incident authority | NOT VERIFIED | Redacted ownership/recovery process and named role acceptance; no login secrets |
| Audit logging/export and privacy | NOT VERIFIED | Available events, access, retention/residency, incident evidence capture and tamper boundaries |
| CPX42 nbg1 stock and account quota | NOT VERIFIED | Dated account-specific read-only evidence supplied by owner; public catalog listing is insufficient |
| Customer VAT and payable quote | NOT VERIFIED | Redacted billing treatment and itemized dated quote for exact resources/window; no billing credentials |
| Provider contract/DPA, subprocessors and support access | NOT VERIFIED | Qualified review of actual contract, support/telemetry locations, access and transfers |
| App/log/runtime-secret and control-plane processing locations | NOT VERIFIED | Data-flow/location matrix distinguishing Germany-only primary workload from provider metadata, support, audit, DNS/certificate and any later backup processing |
| Host usable RAM/disk, encryption and patching | NOT VERIFIED | Approved capacity/security evidence from a separately authorized target; no hosted measurement here |

Account acceptance remains **OPEN**. No Hetzner account was accessed, authenticated or changed. No password, API token, SSH private key, MFA recovery code, billing credential or unredacted customer record was requested/retrieved/stored. Original local environment files were not read. Germany compute residency alone cannot establish every support/control-plane/subprocessor location.

## 4. Network and access review

**VERIFIED source facts, not hosted enforcement:** [staging template](../../../deploy/docker-compose.staging.yml) publishes Caddy80/443; PostgreSQL5432, API8000, web3000 and ClamAV3310 use container expose without host port publication. This is not a firewall/egress policy. The base default Compose network is not marked internal and has no Mo-only source-address rules. [release helper](../../../scripts/release_images.py) preserves that template while binding immutable image IDs; it does not itself establish a host outbound deny policy.

The [Redis fragment](../../../deploy/redis-internal.yml) has no published port, an internal rate-limit-store network, UID999:1000, read-only root, dropped capabilities and no-new-privileges. [Redis release integration](../../../scripts/release_redis.py) attaches API/worker to default plus that private network. Do not generalize Redis's isolation to every service. The disposable [campaign](../../../scripts/integration/campaign.py) explicitly makes its default network internal and removes Caddy host ports; its isolated test topology is not evidence that the staging template already denies outbound traffic.

[Edge configuration](../../../deploy/Caddyfile) overwrites forwarded client identity for the API and strips client-supplied nonce/CSP inputs to Next.js. **Next.js owns the per-request nonce page CSP; Caddy forwards it**, with an asset/error fallback. Retain exact origins, sibling approved domains, secure/HttpOnly/SameSite cookies, trusted-proxy boundaries, authorization and owner isolation. The API image uses UID10001; this does not prove host filesystem/secret permissions or blanket hardening of all services.

The following matrix is **PROPOSED**, with no actual rules or settings changed:

| Path | Proposed access boundary | Acceptance evidence still required |
|---|---|---|
| Operator -> host/control plane | Mo only, MFA/least privilege and reviewed SSH access from approved source addresses; no invented IP/CIDR, no key generation | Named account/source inventory, deny/revoke/emergency tests, provider and host boundaries incl. IPv6 |
| Tester -> Caddy TLS edge | Restricted Mo-only access; public reachability not approved. No public Admin/DB management. TLS/DNS/ACME only under later exact authorization | Reviewed domain/certificate method, ingress refusal from unapproved sources, actual TLS and expiry evidence |
| Edge -> web/API | Only intended reverse-proxy routes and approved sibling origins; retain nonce/CORS/cookies/proxy protections and authentication | Header spoof, CSP injection, hydration, session/owner/CORS and origin-negative tests at intended edge |
| API/worker/migrator -> PG16 | Private database; app/checkpoints in SAME database/public schema; distinct least-privilege app/migrator/recovery roles proposed | Role/privilege, persistence and recovery-GUC/lock qualification; no public port; migration independently authorized |
| API/worker -> Redis | Private authenticated limited ACL and namespace; no public6379; current 37 bucket decisions stay unapproved | ACL denial, shared counters, unavailable/readiness/429/503/Retry-After and restart policy evidence |
| API/worker -> ClamAV / storage | Private scanner; private owner-scoped document and shared knowledge/index filesystem; never web-public | Scanner refusal/freshness plus actual UID/access/private-root/volume identity tests |
| Any service -> internet | Default-deny proposal for IPv4/IPv6; deny paid AI/embedding/OCR/email/OIDC and unapproved telemetry; review only necessary OS/signature/DNS/time/certificate/transport endpoints | Reviewed hostname/IP/TLS enforcement design, dynamic destination/DNS-bypass handling, allowed/denied egress tests. Do not claim a cloud L3 firewall alone enforces all hostname restrictions |
| Monitoring/admin/logs | Private Mo access; safe bounded identifiers/metadata, no candidate content/secrets; Germany-only primary logs | Reviewed fields/access/retention, meaningful redaction, on-call/alert evidence; no paid collector or real email enabled |

Runtime secrets need a proposed Germany-only delivery/rotation/revocation design, read-only non-root access tests, and exclusions from layers/manifests/logs. Existing development secrets/databases must never be copied. No development impersonation header/fallback may be exposed as hosted authentication. Chroma is a local PersistentClient in [vectorstore](../../../src/copilot/vectorstore.py), not an approved new public index service.

Threat cases remain **OPEN**: overprivileged operator, exposed service/Admin ports, forwarded-header spoofing, nonce/secret leakage, unintended external calls, stale signatures/certificates, misleading readiness, host compromise, unsupported provider data locations and loss of the single failure domain.

## 5. Capacity model — qualification OPEN

The approved planning shape is not a CPX42 benchmark. Shared vCPU contention, actual guest MemTotal, filesystem overhead, peak workload and owner thresholds are **NOT VERIFIED**. No arbitrary numeric RSS, QPS or latency acceptance is invented.

| Resource component | Existing observation / model input | Missing sizing evidence |
|---|---|---|
| CPU and memory | 8 shared vCPU /16 GB advertised; actual guest units and competing tenancy unknown | Kernel/Docker overhead and simultaneous peak RSS/CPU/IO for Next/Caddy, API/worker, PG, Redis, ClamAV and embedded Chroma; job/concurrency limits and margin |
| OS/container storage | 320 decimal GB ≈298.02 GiB before filesystem overhead | Guest usable blocks, OS/updates/log/journal/Docker overhead; host encryption/reserved-space impact |
| Images and transfer archives | Current immutable IDs/hashes VERIFIED; API/worker/migrate share one backend image | Engine deduplicated allocated bytes incl. common layers; web/operator/PG/Redis/ClamAV/Caddy images, retained rollback release, tar archives/import peaks. Artifact ZIP size and image IDs are not deployed disk size |
| PG16 application/checkpoints | Same database/public schema is the qualified recovery path | Data/index/WAL/temp/migration-growth budget, retention/maintenance peak and consistent backup staging |
| Documents / knowledge / embedded Chroma | Private shared roots exist in code; no separate public index daemon | Licensed/synthetic dataset bounds, index-building/rewrite peaks, duplicate imports and retention; no original asset sizing/import |
| Redis | Start script sets maxmemory64mb, noeviction; RDB save disabled and AOF off | RSS/allocator/client/Lua overhead and counter cardinality/restart-loss acceptance. Do not budget invented Redis disk persistence; PG retains monetary/durable run state |
| Scanner definitions / Next / logs | EICAR fixture and real daemon function exercised offline | Genuine-definition download/reload peaks, signature storage, node/process/cache/log growth and bounded cleanup/rotation |
| Restore / upgrade / scratch | New-target synthetic recovery function VERIFIED, not a full-size remote recovery | Simultaneous source/target/archives/sealed working set, PG restore/temp/reindex and upgrade/import scratch; independent target scope/location |
| Growth / cleanup / reserve | H05 requires at least100 GiB free after images PLUS growth/restore headroom | Approved growth horizon, occupancy thresholds, cleanup limited to new authorized artifacts and independently demonstrated remaining space |

Transparent disk acceptance equation, in GiB: **OS + deduplicated images + retained archives + PG/WAL/temp + document/knowledge/index + definitions/logs + upgrade scratch + restore scratch + growth allowance + 100 ≤ actual usable guest disk**. Avoid counting a shared image once per API/worker/migrator and avoid double-counting common image layers. A 100 GiB reserve is a floor, not permission to consume restore/growth margin.

Nominal subtraction gives **298.02 −100 ≈198.02 GiB** before the other components and filesystem overhead. These unknown inputs are not zeros. Memory acceptance similarly needs measured simultaneous peak plus OS/Docker and safety margin within actual usable RAM; Chroma/page-cache/private index activity may overlap API/worker allocations. No measured margin or approved peak threshold exists in this packet.

Current f62310ee CI artifact measured **80,705,982,464 bytes (~75.16 GiB) free before campaign** and **80,406,179,840 bytes (~74.88 GiB) after cleanup**. The campaign's code guard is only **8 GiB** free after builds. Those observations support that functional run; they **do not satisfy or test the distinct 100 GiB staging reserve**, measure total image/archive footprint, or establish CPX42 headroom.

The campaign uses an internal CA, no ACME, EICAR-only signatures, a tiny synthetic dataset and same-host container/volume targets. It is not genuine signature coverage, realistic dataset recovery, host-failure recovery, peak-load measurement, multi-host HA or German-host qualification. One host remains one failure domain; two API/worker processes do not change that.

**Capacity acceptance OPEN / implementation BLOCKED on evidence.** If measured requirements exceed the one included disk/VM, require separate scope approval; do not buy space, resize, change SKU or weaken the reserve.

## 6. Cost, quota and resource-risk inventory

The existing [S1 itemized rate model](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md#itemized-authorized-scope-estimate) is preserved as a **published estimate**, not an account-specific quote. No new provider account/price/order check was performed for this submission. Rate evidence was checked publicly on27October2026; account tax/stock/quota remain NOT VERIFIED.

UTC-calendar model assumptions: 88 October hours and632 November hours, using the separately applied monthly compute/IP caps; exact billing timezone/proration/rounding must be confirmed in the payable quote.

| Component | Published planning model / status | Unpriced or scope risk |
|---|---|---|
| CPX42 included disk | 88 ×EUR0.1114 + November EUR69.49 cap = EUR79.2932 net | Actual stock/quota, capacity and binding rate NOT VERIFIED |
| One primary IPv4 | 88 ×EUR0.0008 + November EUR0.50 cap = EUR0.5704 net | Counts as separate billable resource until removed |
| IPv6 / one private network / firewall | No added modeled service charge | Still need access/design and actual account quote; no gateway/load balancer/extra VM |
| Aggregate modeled net | EUR79.8636 | No credits, managed-service or support assumption |
| Illustrative19% VAT / gross | Unrounded tax EUR15.174084; gross EUR95.037684, approximately EUR95.04 | Actual customer VAT and invoice line rounding NOT VERIFIED; German hosting does not determine tax |
| Extra volumes, snapshots, backup objects/copies, restore target | Excluded from current resource authorization | Dated retained-GB/versions/transfer/scratch/teardown quote and separate scope decision required |
| Paid monitoring/secrets/KMS/registry, extra instances | Excluded; no added spend authority | Independent custody/resilience may require a separately approved existing facility or priced addition; not assumed free |
| Egress / transport / retained evidence | Zero extra charge only within verified included allowances | Actual transfer/restore repetition, overage blocks and tail retention must be priced/bounded; alerts do not stop traffic |
| Teardown / rounding / accrued tax | No separate deletion fee established; residual costs unpriced | Powered-off VM and surviving IP/copies may bill; reserve headroom, inventory and final invoice confirmation required |

For comparison, an uncapped720-hour compute+IPv4 model gives EUR80.784 net /EUR96.13296 at illustrative19%. Neither number is a payable promise. At illustrative19% the capped model leaves about EUR54.96 below EUR150; this is **unallocated contingency**, not permission to add excluded services.

Mo remains accountable for daily accrued/forecast all-authorized-charge review, including tax and retention/teardown exposure; stop new expenditure before the ceiling and arrange timely approved deletion at expiry. No alert, account setting, scheduler, purchase or deletion is configured. Do not claim provider-native hard-cap enforcement, automatic expiry cleanup or an approved lower numeric shutdown threshold. Actual full payable affordability remains **NOT VERIFIED**.

## 7. All 16 S2 acceptance entries

This is a one-to-one expansion of the existing checklist; no entry is dropped. Roles below express accountability/proposed review needs, not new appointments. Mo is the only named operator; security/legal/database/backup/independent-custody/incident reviewers remain unappointed unless separately recorded. Every unaccepted gate stays **OPEN**, including where evidence code is VERIFIED.

| # / control | Existing evidence and limit | Additional evidence / acceptance | Accountable role, cost and security dependency | Separate authority needed | State |
|---|---|---|---|---|---|
| 1 Account/MFA/IAM | Named operator/project in H01/H02; actual account controls NOT VERIFIED | Redacted ownership/project/MFA/IAM/recovery/audit/billing-access/DPA evidence; least-privilege/revocation review | Mo; security/privacy reviewers unappointed; account-support/retention cost and processing locations must be reviewed | Owner accepts exact access design; no login/configuration here | OPEN |
| 2 SKU/quote/capacity | Published CPX42/rate model; CI free space is not staging sizing | Stock/quota/customer-tax quote, measured guest RAM/disk/peaks/restore budget meeting ≥100 GiB reserve and approved limits | Mo + engineering review; no additional resource assumed; overload/full disk threatens availability and recovery | Revised owner scope if cost/capacity cannot fit | OPEN |
| 3 Network/access | Staging/Caddy source and offline spoof/CSP tests; base network is not default-deny | Mo-only ingress/admin, private services, reviewed IPv4/IPv6 egress/TLS/DNS and negative probes | Mo; security reviewer unappointed; added gateway/VPN/domain/service cost excluded; protect identity/private data | Exact configuration/domain/egress authorization before changes | OPEN |
| 4 PostgreSQL | One-shot0048 dependency, same-DB checkpoint recovery offline | Private PG16 role/privilege, storage/encryption, migrator/recovery locks/GUCs and new-target rehearsal | Mo; qualified DB/recovery role unappointed; data/WAL/scratch cost and custody affect recovery | Explicit new-target migration operation; never original DB | OPEN |
| 5 Redis | Internal network/ACL/non-root, memory64mb/noeviction/no persistence; 37 bucket worksheet | Owner policy for all37, ACL/auth and shared-burst/outage/restart/readiness/Retry-After proof | Mo + security/product decision; memory overhead bounded; counter loss/local fallback consequences explicit; PG remains monetary authority | H-REDIS-POLICY and topology/access decisions, not bulk approval from VM choice | OPEN |
| 6 Runtime secrets | UID10001 image, secret exclusion and store contracts offline | Germany-only read-only delivery, actual UID10001/Redis999 access/deny/canary, rotation/revoke/audit evidence | Mo; secret custodian unappointed; external paid store excluded; original secrets never copied | Named delivery/custody design approval before any key or credential action | OPEN |
| 7 Encryption/custody | Sealed recovery and derived manifest authentication verified offline | Host/disk/key/ledger/master-key separation, independent custody/escrow, rotation/loss/wrong-key proof | Security/custodians unappointed; independent facilities may need separate resource approval; no claim of independent signature from derived MAC | Custody/encryption approval; no new signing/encryption key here | OPEN |
| 8 Off-host backup/ledger | Logical separate-volume transfer/new-target restore on one disposable host | Separately controlled Germany/France provider/account/copies and latest independent erasure head; authenticated transfer/new-host receipt/restore | Mo coordinates; backup/ledger operators unappointed; external storage/transfer/target currently excluded | Separate provider/account/resource/transfer authority; no same-host substitution | OPEN |
| 9 Retention/erasure | Offline reapplication/rewrite and audit contracts | Owner/counsel schedule for app/log/key/backups/versions/snapshots, disposal and current-head verification | Privacy/counsel unappointed; retention/rewrite/egress cost; immutable copies versus erasure review | Named owner/legal acceptance; engineering35-day defaults not approved | OPEN |
| 10 RPO/RTO/rollback | Offline new-target restore/quarantine/compatibility controls | Numeric objectives/cadence/scale, recovery/incident roles, timed approved fault/drain/unknown-usage reconciliation and compatible rollback | Mo coordinates; independent reviewers unappointed; separate-target/standby resources not authorized; preserve unsettled usage | Named recovery/rollback authority and revised target scope; hold release separately gated | OPEN |
| 11 ClamAV | Real daemon/EICAR fixture and unreachable refusal; genuine coverage/freshness NOT RUN | Supported image/digest, genuine definitions/update endpoints, freshness threshold and restart/stale/outage proof | Mo + security reviewer; RAM/disk/egress allowance and privacy review; stale/unreachable uploads must not be treated safe | Signature/update/freshness/alert policy approval before network/config changes | OPEN |
| 12 Monitoring/incident | Readiness/worker/scanner/PG/Redis/budget/hold signals offline | Private Germany-only logs, bounded safe fields/retention, collection/on-call/alert delivery and response/recovery proof | Mo; incident/backup responders unappointed; paid collector/paging excluded; single host loses its own monitoring | Reviewed monitoring/access/notification design and any separate service scope | OPEN |
| 13 Spend/teardown | Owner EUR150 inclusive cap and fixed expiry | Actual billing/forecast visibility and alerts, stop-before-cap reserve, all-resource deletion/retention inventory and final invoice procedure | Mo billing/shutdown; tax/overage/retention-tail included; no alert hard-stop assumption | Explicit later teardown of newly authorized resources, never original/private assets | OPEN |
| 14 Immutable release | Same backend API/worker/migrate IDs, matching web, manifest/rollback source checks | Approved real-domain SHA/origin/bundle/anchors, offline transport/load identity and host proof | Mo/release review; current CI example-domain images are not a hosted release; archive footprint/transport costs unresolved | Exact bundle/transport/target approval; no registry/remote load here | OPEN |
| 15 Language/features | Strict hosted activation guard, zero qualified locales; refused external scenarios retained | Reviewed no-bypass refusal tests and formal OD-STAGING-LANGUAGES/native/legal/source protocol | Product/security/native/legal qualifiers unappointed; no paid quality budget implied; retain disabled features/Russian exclusion | Legitimate separate qualification; no synthetic-scope/auth/language bypass | OPEN |
| 16 Deployment entry | No authority beyond S1 documentation and this S2-A review preparation | Fresh baseline/quote/window, all required signed acceptances, exact permitted resource operations/target/migration/test/rollback plan | Mo plus required reviewers; change in resource/cost/scope needs renewal; unknown usage/holds persist | Separate explicit owner deployment/provisioning authorization after prerequisites | OPEN — execution BLOCKED |

Source decisions: [H/R/S/G worksheets](WAVE4_TASK08_OWNER_DECISIONS.md), [preflight and S0–S8 boundaries](WAVE4_TASK08_AUTHORIZATION_PREFLIGHT.md), [release tracker](RELEASE_READINESS_TRACKER.md), [recovery runbook](../BACKUP_RESTORE_RUNBOOK.md). No state is accepted merely by writing a design.

## 8. Scope conflicts and smallest separately decidable additions

| Conflict | Current verdict | Smallest decision to investigate, not an authorized addition |
|---|---|---|
| One VM versus independent off-host backup/ledger | BLOCKED: same-host copies/volumes do not survive host loss or establish independent account/key authority | Owner identifies an already qualified independent Germany/France facility, or separately authorizes one bounded encrypted backup store with retained GB/version/egress/expiry quote; independently controlled latest ledger/head still required |
| One operator/host versus independent key/erasure custody | BLOCKED on accepted custody separation | Name independent custodian/access/escrow arrangements using reviewed existing facilities if suitable; otherwise separately price/authorize exact storage/key service. Do not invent a second operator or free service |
| New-target recovery versus no extra instance/volume | BLOCKED for any drill needing a resource outside current list | Owner specifies a separately authorized isolated existing target with verified capacity/location, or a temporary bounded recovery target with explicit cost, duration and disposal. No in-place overwrite or automatic second VM |
| Single-host monitoring/availability | OPEN: host failure can remove both services and local observations | Define incident/on-call/manual evidence and availability limits; if independent alerting is required, choose approved existing channel or separately authorize the smallest collector/channel. A paid monitoring vendor is not presumed mandatory or approved |
| Nominal disk/RAM versus real growth/restore peak | NOT VERIFIED | Obtain measurements and data bounds first. Only if it fails, request the smallest justified additional capacity/scope; no silent volume/VM purchase or SKU substitution |
| Language bootstrap and strict authentication | BLOCKED for unqualified positive hosted journeys | Owner/reviewers decide the legitimate protocol under OD-STAGING-LANGUAGES without fake records, dev-header impersonation, or production/staging guard bypass |

The current one-VM scope **does not itself satisfy later independent backup/custody/new-target recovery requirements**. An already available independent facility might avoid new billing, but its use, processing/custody and transfer still require separate approval. No complete larger resource set or payable total is known, and no claim is made that it can fit EUR150. Do not weaken requirements or spend the reserve to force a fit.

## 9. S2-B owner-evidence and separate scope decisions

Only redacted, noncredential evidence is appropriate: project/account ownership and Mo-only MFA/IAM/billing/audit/recovery facts; dated nbg1 CPX42 stock/quota/customer-tax quote; contracts/DPA/subprocessors/support and data-flow locations; existing image/archive/resource measurements; named qualified reviewers/custodians; proposed backup/ledger/recovery facility and separate quote; retention/cadence/RPO/RTO targets and all37 Redis bucket decisions.

Before the **first billable action**, require actual account/security/location/quote/capacity evidence, accepted network/secret/PG/Redis/scanner/monitoring/recovery designs, resolved excluded-resource needs, the unchanged valid window/aggregate ceiling, reviewed real-domain immutable bundle/target plan, and a fresh separate owner authorization listing exact resource mutations. No purchase follows from S1 documentation, green CI or merging this PR.

Recommended next milestone: **S2-B redacted owner-evidence and separate resource-scope decision review**. It is not execution. No provider login, credentials, account configuration, keys, cloud copies, DNS, publication, remote image load, database migration, real data, paid provider/email/OIDC activity, language activation, monetary reset or recovery-hold release is permitted here.

Suggested next prompt, only when separately sent by the owner:

> Ask4Mo — S2-B owner-evidence and resource-scope review only. Review the S2-A packet and current main/CI. Assess only voluntarily supplied redacted project/MFA/IAM/stock/quota/tax/contract/capacity evidence; retain NOT VERIFIED wherever absent. Prepare separate decision options for independent Germany/France backup and erasure/key custody, an isolated recovery target, monitoring, retention/RPO/RTO and all37 Redis bucket policies, with itemized costs and ownership. Do not approve any option, extend the fixed window, spend the EUR150 reserve or change H01/H02 without a new explicit owner decision. No provider/account/credential access, configuration, key generation, purchases, provisioning, deployment, database access/migration, paid AI/email/OIDC, language activation or hold release. Keep all unaccepted S2 gates OPEN, OD-BUDGET OPEN, 40/45 and PG/LG acceptance unchanged. Submit a focused review-only PR; do not merge.

## 10. Review disposition and preservation

**S2-A review packet PROPOSED; all16 acceptance entries OPEN; execution BLOCKED.** Source/CI/offline facts above are VERIFIED only in their stated scope. Account controls, binding tax/stock/quota quote, host measurements, legal processing review, independent custody and operational proof remain NOT VERIFIED / NOT RUN. No application/runtime/deployment setting, approval object or historical Task07 evidence is modified by this submission.

Pre-branch actual inventory: **50 worktrees (31 dirty), 318 local branches, 39 untracked files, 203 protected/untracked metadata records, 23 unique local commits not reachable from origin/main**. Metadata only for protected databases/env/assets; no private content opened or copied. The new isolated documentation worktree/branch is additive; preserve every original branch tip and existing checkout.

Five layers remain distinct: **engineering40/45** (00A/00B/07B/07C/08A OPEN); **baseline CI7/7 VERIFIED** (PR-head checks separate); **hosted staging NOT RUN**; **human qualification OPEN**; **PG/LG acceptance unchanged**. Only historical PG-11 is accepted; zero hosted-qualified languages. OD-BUDGET and all other unresolved owner decisions remain OPEN. No production/release acceptance is added.
