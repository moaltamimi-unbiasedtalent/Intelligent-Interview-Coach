# S2-B — Owner-Evidence and Readiness Decision Review

**Status: PROPOSED — FOR OWNER REVIEW.**

**Review date: 28 October 2026.**

**Decision boundary: documentation/evidence preparation only; infrastructure execution BLOCKED.**

No S2 acceptance, owner appointment, resource purchase, deployment permission or production/language approval is created by this packet.

## 1. Source and qualification record

Authoritative main: `5c76f1ea144663bc17a8972827d368f306a0a756`.

[PR #280](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/280) merged from `320ea2a74a354f983e2e07639f570f5c9bdb4f53`. The merge parents are previous main `291eb523afbc099a9d587cb73e96586c9c83876d` and that PR head. Both reviewed head and merged main have tree `2211458455e2f646073d198b0cbee431b2f9a992`.

Every workflow below is a main-push run against the authoritative main, **SUCCESS, attempt 1**:

| Workflow | Source-bound run |
|---|---|
| CI | [40602784672](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784672) |
| Immutable release | [40602784475](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784475) |
| Migration image | [40602784668](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784668) |
| Durable admission | [40602784487](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784487) |
| AI budget | [40602784729](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784729) |
| Redis | [40602784549](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784549) |
| Encrypted recovery | [40602784582](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784582) |

Main CI recorded **8,737 passed / 180 skipped**, reconciling all 8,917 collected backend tests; frontend **1,574 passed**. PR-head Browser E2E remains separately attributed evidence.

### Current main artifacts

| Evidence | Verified finding |
|---|---|
| [CSP artifact 12779756614](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784475/artifacts/12779756614) | Complete sign-in, authenticated reads, nonce/spoof checks, negative injection and logout; zero unexpected console/page errors |
| CSP diagnostic counts | Eleven `ERR_ABORTED` requests recorded separately; two expected 401 console messages and two intentional CSP refusals; no dropped events |
| [Campaign artifact 12779358359](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784475/artifacts/12779358359) | **29 PASS / 0 FAIL / 0 SKIP / 6 NOT RUN**; three connected-browser journeys passed |
| [Release metadata 12780765482](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40602784475/artifacts/12780765482) | Matching source, images, manifest and disposable schema `0048_agent_run_controls` |

Immutable local Docker image identities:

- Application: `sha256:0ecbbf3ed7d109040ce9c885fcdf411931a14622286c351efd7ca42ac1ad5c46`
- Frontend: `sha256:2ee6693c0a086145a9764b5b0beb6ca02ddbb38cce0feb122d9a5977a94938e2`
- Release manifest SHA256: `54079772e526a272c7cccf90c52989c4523d01523785c495d18e398c143b93c8`

API replicas, workers and migration services use the same application image. These are local immutable image IDs, **not registry distribution digests or hosted-release approval**.

The campaign remains `PARTIAL_EXTERNAL_DEPENDENCIES`. Its six NOT RUN scenarios are:

1. New hosted-language registration and interviews.
2. Positive language interview/career journeys.
3. Live AI quality and embeddings.
4. Real email/OIDC.
5. Hosted TLS and genuine signature freshness.
6. Recovery-hold release.

Synthetic qualification does not establish Hetzner capacity, German contractual residency, independent off-host custody, genuine scanner freshness, hosted language qualification or production readiness.

### Historical evidence

[Historical immutable run 40582511816](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40582511816) remains **FAIL, attempt 1**, on `291eb523…`, with 13 unexpected console errors and no retained messages. Its root cause remains **UNPROVEN**.

Subsequent passes establish passing current-source runs, not historical attribution. Historical Task 07/08 records, failed attempts and earlier source/image bindings remain unchanged.

## 2. Exact H01/H02 envelope

The [S1 owner record](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md) authorizes **S1 documentation only**:

- Hetzner Cloud, Nuremberg `nbg1`, intended isolated project `ask4mo-staging-eu`.
- Exactly one CPX42 x86 Linux VM, included **320 GB** system disk.
- One primary IPv4, IPv6, one private network and firewall configuration.
- Mo Al-Tamimi: sole operator/tester and accountable operations, billing and shutdown owner.
- Germany-only primary application, database, document, index, operational-log and runtime-secret processing.
- EUR150 aggregate ceiling, including applicable VAT and all authorized charges.
- Fixed window: **28 October 2026 09:00 CET inclusive → 27 November 2026 09:00 CET exclusive**.
- No automatic extension, renewal, scaling, fallback SKU or additional paid resource.

Future independently controlled encrypted backups may be in Germany or France only after separate approval of provider/account, contract, custody, retention and procedure. No backup purchase is presently authorized.

The date, ceiling, source merge and green CI grant no execution authority.

## 3. Complete S2 acceptance matrix

Control authority remains the [S2 checklist](WAVE4_S2_SECURITY_ENTRY_CHECKLIST.md), [S2-A packet](WAVE4_S2A_SECURITY_CAPACITY_EVIDENCE.md), [owner worksheets](WAVE4_TASK08_OWNER_DECISIONS.md) and [owner register](../OWNER_DECISION_REGISTER.md).

**Verified engineering evidence is supporting evidence, not hosted acceptance.**

**NV means NOT VERIFIED.** No new account-specific evidence was supplied with this task.

### Evidence, proposed controls and acceptance criteria

| # / Control | Existing verified evidence | Proposed control | Missing evidence / minimum acceptance criteria |
|---|---|---|---|
| 1 Account/MFA/IAM | S1 names project and operator; actual account controls NV | Isolated project, Mo-only least privilege, MFA and recovery | NV: ownership, project ID, MFA, IAM, audit and recovery. Accept dated redacted proof and qualified access review. |
| 2 SKU/quote/capacity | Published planning model; disposable image/campaign results | One CPX42 within exact scope and measured limits | NV: stock, quota, tax quote and guest capacity. Require payable quote, workload bounds, measured peaks and ≥100 GiB reserve. |
| 3 Network/access | Offline proxy/CSP/ownership checks; base Compose is not default-deny | Mo-only ingress/admin; IPv4/IPv6 default-deny; private services | NV: intended addresses/domains, firewall/egress enforcement. Require approved design and authorized positive/negative probes on both IP families. |
| 4 PostgreSQL | PG16, same-database checkpoints, one-shot migration dependency and recovery tested offline | Private PG16; separate app/migrator/recovery privileges | NV: host roles, encryption, storage and recovery privileges. Require reviewed permissions and authorized fresh-target migration/recovery proof. |
| 5 Redis | Shared controls tested; 37 buckets; noeviction; RDB/AOF disabled | Private authenticated ACL boundary and explicitly accepted failure policies | NV: all 37 decisions and restart-loss acceptance. Require signed dispositions plus ACL, outage, restart, readiness and Retry-After evidence. |
| 6 Runtime secrets | Non-root image and secret-exclusion controls | Germany-only read-only delivery with rotation/revocation | NV: delivery facility, custody and host permissions. Require intended-UID allow/deny canaries, audit, rotation and revocation procedure. |
| 7 Encryption/key custody | Sealed restore and derived manifest authentication tested offline | Host encryption and independent key/ledger/master-key custody | NV: custodians, escrow, separation and key-loss procedures. Require qualified design and separately authorized wrong-key/recovery tests. |
| 8 Off-host backup/ledger | Logical separate-volume recovery on one disposable host | Independent Germany/France storage and trusted latest erasure head | NV: actual facility/account, copies, independent custody and receipts. Require separately approved transfer and genuinely independent-target restore. |
| 9 Retention/erasure | Offline erasure/reapplication and audit tooling | Approved schedules across every data/copy/key class | NV: owner/legal schedule and disposal policy. Require retention-versus-erasure reconciliation, version inventory and destruction evidence requirements. |
| 10 RPO/RTO/rollback | Offline hold, reconciliation and compatibility controls | Named recovery roles; measured objectives; compatible image rollback | NV: numerical targets, cadence, scale and authority. Require approved timed drills preserving unsettled usage; no automatic database downgrade. |
| 11 ClamAV | Real daemon with synthetic EICAR definitions; refusal paths tested | Genuine definitions, approved updates and freshness controls | NV: coverage, freshness threshold, endpoints and responsibility. Require approved genuine-definition, stale/unreachable, restart and alert verification. |
| 12 Monitoring/incident | Existing readiness, worker, scanner, database, budget and hold signals | Private German logs, bounded alerts and named response | NV: collection, retention, on-call and escalation. Require safe-field review, controlled alert/acknowledgment/recovery proof and host-loss procedure. |
| 13 Spend/teardown | Written EUR150 ceiling, fixed expiry and Mo accountability | Daily accrued/forecast review, alerts and reviewed teardown | NV: payable charges and billing controls. Require complete inventory, stop-before-ceiling reserve, deletion confirmation and final invoice procedure. |
| 14 Immutable release/transport | Current source/image/manifest identity verified offline | Reviewed real-origin release and anchored offline transport | NV: real domains, intended target and transport approval. Require matching bundle/anchors and authorized load/identity verification; no implicit registry use. |
| 15 Language/features | Strict guards; zero hosted-qualified languages; refusals retained | Disabled features remain disabled; legitimate qualification only | NV: accepted language protocol and reviewers. Require no-bypass refusal evidence and separate native/legal/source qualification before activation. |
| 16 Execution entry | S1 documentation-only approval; current offline qualification verified | Fresh, exact-operation owner authorization after prerequisites | NV: prerequisite acceptances and execution grant. Require current source/quote/window, accepted controls and explicit resource/migration/test/rollback scope. |

### Ownership, independent review, risks and authority

Mo owns evidence collection and decision coordination. Review roles below are **required but unappointed**; this table grants nobody operational access.

| # | Evidence owner | Required independent review | Principal commercial/security/dependency risk | Separate authorization needed | State |
|---|---|---|---|---|---|
| 1 | Mo | Security/privacy | Takeover, excessive privilege, unsupported processing locations | Exact account/access design and any settings changes | OPEN |
| 2 | Mo | Engineering/cost | Unorderable SKU, tax overrun, memory/disk exhaustion | Revised scope for any capacity/resource/price change | OPEN |
| 3 | Mo | Security/network | Public exposure, identity spoofing, unintended egress | Exact network, domain, TLS and probe operations | OPEN |
| 4 | Mo; specialist pending | Database/recovery | Excessive privilege, data loss, WAL/scratch exhaustion | Fresh-target migration/recovery; never original DB | OPEN |
| 5 | Mo | Security/product | Counter loss, fallback consequences, availability | All 37 policies and topology/security choices | OPEN |
| 6 | Mo; custodian pending | Security/privacy | Secret disclosure, excessive UID access, excluded service cost | Delivery/custody and credential lifecycle actions | OPEN |
| 7 | Mo; custodians pending | Security/privacy | Shared compromise domain or unrecoverable key loss | Encryption, custody, escrow and key operations | OPEN |
| 8 | Mo; backup custodian pending | Recovery/security/privacy | Host loss, stale ledger, excluded storage/transfer costs | Exact independent facility, transfer and recovery target | OPEN |
| 9 | Mo | Counsel/privacy | Excess retention, premature deletion, immutable-copy conflict | Legal schedule and any deletion operations | OPEN |
| 10 | Mo; recovery roles pending | Independent recovery/database | Unmet recovery objectives, unsafe rollback, lost usage accounting | Target/drill/rollback authority; hold release separately gated | OPEN |
| 11 | Mo | Security | Unsafe uploads, stale definitions, RAM/disk/egress demand | Update/freshness/alert policy and network changes | OPEN |
| 12 | Mo; responder pending | Security/privacy/operations | Undetected host loss, private logs, extra service costs | Monitoring/access/notification design and additions | OPEN |
| 13 | Mo | Cost/operations | Continuing VM/IP/copy charges and expiry overrun | Later disposal of specifically authorized new resources | OPEN |
| 14 | Mo; release reviewer pending | Release/security | Wrong bundle/origin, tampering, archive/transport footprint | Exact bundle, destination and transport/load actions | OPEN |
| 15 | Mo | Native/legal/source/security | Unauthorized language or feature activation | Independent qualification and explicit activation decision | OPEN |
| 16 | Mo | All applicable reviewers | Unresolved dependencies or unauthorized execution | Fresh written owner grant naming exact permitted actions | OPEN |

Redis remains rate-limit infrastructure; durable PostgreSQL admission, settlement and unknown monetary usage remain authoritative. The two observe-only buckets and disabled features must not be silently changed.

## 4. Owner-evidence collection checklist

Supply redacted, noncredential evidence only. Each item needs an observation date, source reference, scope, evidence owner and proposed reviewer.

- Project/account ownership and private identifier mapping; meaningful redacted project reference.
- MFA status, Mo-only roles, billing visibility, recovery/revocation process and audit capabilities.
- Account-specific CPX42 `nbg1` stock/quota evidence and complete payable quotation.
- Tax treatment and gross totals without publishing personal billing addresses, tax identifiers or payment details.
- Contract/DPA, subprocessors, support access and data-flow/location review.
- Intended ingress/admin sources, domains, TLS approach and IPv4/IPv6 egress design.
- Guest usable RAM/disk, deduplicated image/archive footprint, workload bounds and simultaneous resource measurements.
- Named reviewers/custodians, independent facility proposals and separate quotes.
- All 37 Redis decisions, retention schedules, numerical RPO/RTO and recovery cadence.
- Monitoring/on-call, spending review, shutdown, deletion and evidence-retention procedures.

Never supply passwords, tokens, private keys, recovery codes, cookies, original dotenv files or candidate content. Do not perform provider login or new measurements under this packet.

### Commercial qualification

The recorded 27 October public-price model is **historical planning evidence**, not a payable quotation:

| Component | Recorded model |
|---|---:|
| CPX42 compute, included disk | EUR79.2932 net |
| One primary IPv4 | EUR0.5704 net |
| Modeled subtotal | EUR79.8636 net |
| Illustration at 19% VAT | Approximately EUR95.04 gross |

Actual VAT, billing timezone/proration/rounding, allowance/overage, retention and teardown exposure remain NV. IPv6/network/firewall carry no added modeled charge, subject to actual quote verification.

The approximately EUR54.96 modeled contingency grants no additional service authority. Budget alerts are not a provider-enforced spending cap; powered-off VMs and surviving IPs/copies may continue billing.

### Capacity qualification

Advertised GB and RAM are not measured usable guest capacity. A 320 decimal-GB disk is approximately 298.02 GiB before filesystem overhead.

Require:

**OS + deduplicated images + retained archives/rollback release + PG/WAL/temp + documents/index + definitions/logs + upgrade/import scratch + restore working set + growth allowance + 100 GiB ≤ measured usable guest disk.**

Measure simultaneous Next/Caddy, API/worker, PostgreSQL, Redis, ClamAV, embedded Chroma and host/Docker overhead against approved workload limits. Do not invent RAM, throughput or latency margins.

CI’s functional free-space guard does not qualify the 100 GiB staging reserve. Same-host replicas and separate volumes do not provide host-level availability or independent disaster recovery.

## 5. Separate owner/resource decisions

These remain proposals, not accepted additions:

| Decision | Minimum decision content |
|---|---|
| Independent backup and ledger facility | Approved existing facility or separately priced store; Germany/France location, account, contract, custody, versions, transfer and disposal |
| Independent key custody | Named custodian, access separation, escrow, recovery/rotation and reviewed existing facility or separately authorized service |
| Independent recovery target | Qualified existing target or explicitly bounded temporary resource; location, capacity, duration, cost and disposal |
| Monitoring outside the failure domain | Approved existing channel/manual procedure or separately priced collector; privacy, routing and response |
| Operational policies | All Redis buckets; retention/erasure; numerical RPO/RTO; scanner freshness; workload and incident thresholds |
| Any resource/scope change | Exact service/SKU/location, purpose, operators, VAT-inclusive amount, duration and exclusions; no implicit use of contingency |
| Execution entry | Exact permitted mutations and target, prerequisite acceptances, fresh quote/source/window, migration/test/rollback boundaries |

An already owned facility may avoid a new bill, but its use, transfer, custody and location still require approval. No design may waive recovery requirements simply to fit one VM or EUR150.

## 6. Engineering follow-up — legacy CSP violation retention

**OPEN; not implemented by S2-B.**

The new collector is bounded, but the legacy in-page `cspEvents` array remains uncapped. Its stored values are sanitized; no overflow was observed in current qualification.

Expected separate correction:

- Cap retained sanitized violation entries.
- Maintain independent exact violation counters.
- Preserve CSP assertions, refusal behavior and zero-error requirements.
- Add overflow, privacy and failure-path regressions.
- Do not change production CSP configuration or introduce retries.
- Never interpret truncation or unavailable diagnostics as zero failures or PASS.

This follow-up does not establish the historical 13-error cause or prevent documentation preparation.

## 7. Conditional decisions and unchanged readiness

**GO:** S2-B documentation and voluntarily supplied redacted-evidence preparation.

**NO-GO:** infrastructure execution. All 16 controls remain OPEN.

A future execution decision may be considered only after applicable prerequisites are independently accepted, excluded-resource needs receive separate decisions, the quote and fixed window remain valid, and the owner explicitly authorizes exact operations. An expired window, changed resource scope, missing evidence or failed required qualification blocks execution; no automatic renewal applies.

Five-layer status:

- Engineering: **40/45**; 00A/00B/07B/07C/08A remain open/incomplete.
- CI/offline qualification: **VERIFIED on exact main source**.
- Hosted staging: **NOT RUN**.
- Human qualification: **OPEN**.
- PG/LG acceptance: **UNCHANGED**; hosted-qualified languages **ZERO**.

OD-BUDGET remains OPEN. Infrastructure funding does not authorize paid AI. No production authorization, approval-object mutation, language activation or recovery-hold release is granted.

## 8. Preservation record

This section records the preceding read-only packet-preparation review. The later documentation implementation and its additive worktree/validation are reported separately in its review-only PR.

Metadata-only before/after fingerprints matched for:

- 52 worktrees and 320 branch tips.
- 31 dirty worktrees and 39 untracked files.
- 187 protected metadata records.
- 1,582 historical/approval metadata records.
- All 52 Git indexes.

No fetch, reset, clean, source edit, local test run, workflow rerun, provider access, database/secret access or paid call was performed. Historical records retain their original sources and results.
