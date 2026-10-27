# S1 H01/H02 — owner-approved documentation record

**Disposition:** H01/H02 owner-selection, operator and bounded terms are **APPROVED FOR S1 DOCUMENTATION ONLY**. The overall OD-HOSTED execution decision remains **PARTIAL / OPEN**; S1 deployment-entry is **BLOCKED**, and provisioning/deployment are **NOT AUTHORIZED**. S2 items retain independent acceptance gates.

## Provenance and dates

Source: Mo Al-Tamimi's explicit written approval in the current Codex conversation, received **27 October 2026**. The quoted statement below is the authority, not a previous recommendation, PR merge or the task instructions. The source retains its earlier draft heading; the subsequent affirmative statement expressly approves every stated field, while limiting authority to S1 documentation. Both are preserved verbatim below.

The owner's message does not supply a separate signature time-of-day. Do not manufacture one. Engineering verification began **2026-10-27T19:00:35Z** (tool clock); that is a verification timestamp, not an owner signature timestamp.

Approved effective window: **2026-10-28T09:00:00+01:00** inclusive through **2026-11-27T09:00:00+01:00** exclusive. UTC equivalents: **2026-10-28T08:00:00Z** through **2026-11-27T08:00:00Z**. Exactly **30 calendar days / 720 hours**. No automatic extension, renewal, scaling or delayed-start rebaselining. Expiry does not authorize destruction of original/private assets; later implementation must arrange timely, reviewed disposal of only newly authorized billable rehearsal resources and preserve required evidence under an approved retention plan.

## Exact owner decision and explicit approval

The following decision text is transcribed from the owner's message. Proposed labels are preserved rather than silently rewritten.

> # Ask4Mo — S1 H01/H02 Owner Authorization
>
> **Status: DRAFT — AWAITING EXPLICIT OWNER APPROVAL**
>
> I, Mo Al-Tamimi, propose the following bounded staging authorization for Ask4Mo R1.0.
>
> **H01 — Hosting and location**
>
> - Provider: Hetzner Cloud.
> - Region: Nuremberg, Germany (`nbg1`).
> - Isolated project: `ask4mo-staging-eu`.
> - Initial infrastructure: one CPX42 x86 Linux virtual machine, including its 320 GB system disk, one primary IPv4, IPv6, one private network and firewall configuration.
> - Primary application, database, document, index, operational-log and runtime-secret processing: Germany only, unless separately approved.
> - Future independently controlled encrypted backups: Germany or France only, conditional upon separate approval of the provider, account, contract, key custody, retention and operating procedure.
>
> **H02 — Ownership and expenditure**
>
> - Accountable operations lead: Mo Al-Tamimi.
> - Shutdown and billing owner: Mo Al-Tamimi.
> - Authorized operators and testers: Mo Al-Tamimi only.
> - Proposed aggregate ceiling: EUR 150, including applicable VAT and all authorized infrastructure charges.
> - Proposed start: 28 October 2026 at 09:00 CET (UTC+01:00).
> - Proposed expiry: 27 November 2026 at 09:00 CET (UTC+01:00), exclusive.
> - Duration: 30 calendar days.
> - No automatic scaling, additional paid resources or budget renewal.
> - The operator is responsible for reviewing charges, stopping new expenditure and arranging timely deletion of billable resources.
>
> **Permitted scope**
>
> Infrastructure-only staging preparation, security checks and synthetic offline application qualification, subject to separate S2 security and deployment-entry approvals.
>
> **Not authorized**
>
> Production deployment, real candidate data, paid AI/embeddings/OCR, transactional email, OIDC activation, public beta, unqualified languages, live billing, additional paid storage, cloud backup provisioning, registry publication, extra instances or budget increases.
>
> This decision does not authorize actual resource provisioning. All outstanding security, key-custody, backup, retention, Redis, privacy, language and operational controls must independently pass their required gates.

Exact subsequent affirmative approval:

> “I, Mo Al-Tamimi, approve the H01/H02 configuration and all dates, locations, services, exclusions and the EUR 150 inclusive-of-applicable-VAT aggregate ceiling stated above. I accept accountability for operations, billing and shutdown. This approval authorizes S1 documentation only, not provisioning or deployment.”

No additional signature, approval marker, runtime activation file, credential, legal review or purchase authority is created by this transcription.

## Ten-field validation

| Required field | Recorded owner decision | Disposition / remaining boundary |
|---|---|---|
| Provider / EU region | Hetzner Cloud / Nuremberg nbg1 | Approved for documentation; no region substitution |
| Account/project / processing locations | ask4mo-staging-eu; primary app/DB/documents/index/logs/runtime secrets Germany only | Named project is intended identity, not evidence of account creation, MFA or verified provider project ID; provider/support/control-plane data flows and DPA still require review |
| Operations lead acceptance | Mo Al-Tamimi; exact statement accepts operations accountability | Recorded; no other reviewer/custodian appointed |
| Shutdown / billing acceptance | Mo Al-Tamimi; exact statement accepts billing and shutdown | Recorded; no monetary-control reset or recovery-hold release |
| Aggregate amount / currency / tax | EUR 150 including applicable VAT and all authorized infrastructure charges | Owner constraint, not provider-enforced hard cap; actual account tax quote NOT VERIFIED |
| Effective timestamp / expiry | 28 Oct 09:00 CET to 27 Nov 09:00 CET, exclusive, 2026 | 30 days; no renewal or automatic shift if implementation is delayed |
| Resource classes / SKU | One CPX42 x86 Linux VM, included 320 GB system disk, one primary IPv4, IPv6, one private network and firewall | No CX43 fallback, extra instance/storage, managed service or paid add-on authorized |
| Operators / access | Mo Al-Tamimi only; isolated from production and original development data/credentials | Named sole operator/tester; least-privilege MFA/network/IAM evidence still OPEN |
| Activities / exclusions | Infrastructure-only preparation/security/synthetic offline qualification; exact exclusions above | S2 security and execution-entry approval still required; no provisioning |
| Attributable written approval | Exact Mo Al-Tamimi statement above, received 27 Oct 2026 | Explicit documentation-only approval; no separate signature time invented |

## Baseline, scope and independent verification limits

Fetched main: **bf579aa5d0e39e2447922fd7af87748a24bd9808**, incorporating PR #277. Seven mandatory main-push workflows are completed SUCCESS on that SHA: CI40541545913; admission40541546097; budget40541546293; Redis40541545867; migration40541545909; immutable40541546270; recovery40541546215. [Main workflows](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions?query=branch%3Amain). No separate authorization-closure PR or later decision was found before this branch. Historical Task 08 preflight JSON and test evidence are not rewritten.

**Selection:** CPX42 only, nbg1 only; no fallback purchase. The official public product catalog advertises **8 shared AMD x86 vCPU / 16 GB RAM / 320 GB NVMe**. Public nbg1 pricing was fetched anonymously on 27 Oct 2026: compute+one primary IPv4 **EUR 0.1122/hour / EUR 69.99 calendar-month cap**, excluding VAT. Catalog active=true is not live stock. Public product pages render unavailable notices; this is not an account-specific stock/quota check.

**NOT VERIFIED:** actual provider account/project existence or MFA, nbg1 orderability, quota, customer billing jurisdiction/VAT, binding account quote, provider processing-location contract, host usable resources, peak memory/CPU/IO, restore headroom. No provider login, credentials, cloud API token, order/create probe or purchase was used. Public catalog lookup cannot complete these checks; retain the resource-specific implementation block until the named owner supplies approved read-only evidence. Do not infer location compliance from EU hosting or provider marketing.

## Itemized authorized-scope estimate

This is the full line-item model for the authorized resource list, **not a complete account-verified payable quotation**. Actual tax and stock are unavailable. EUR figures, before VAT unless labeled otherwise; no credits/discounts assumed.

For the fixed UTC window, October accounts for **88 hours**, November **632 hours**. Applying published per-calendar-month caps separately:

| Item | Published unit / treatment | Window estimate net | Implementation boundary |
|---|---|---:|---|
| One CPX42 compute, included 320 GB system disk | EUR0.1114/hour; EUR69.49/month cap | EUR79.2932 | 88 × 0.1114 + min(632 × 0.1114, 69.49) |
| One primary IPv4 | EUR0.0008/hour; EUR0.50/month cap from combined catalog minus compute tariff | EUR0.5704 | Allocated IP continues billing until removed; exactly one |
| IPv6 | Included/free | EUR0 | No paid network add-on |
| One private network | Included/free | EUR0 | Configuration scope only; no NAT gateway/load balancer/extra VM |
| Firewall | Included/free | EUR0 | Rules/ingress/egress review OPEN |
| Additional paid volumes / restore disks | Excluded | Not purchased | No extra storage allowance hidden in EUR150 |
| Provider backups / snapshots / off-host objects / retained versions | Excluded | Not purchased | Future Germany/France location constraint is not backup-service approval |
| External monitoring / paging / secret manager / KMS / registry | Excluded as additional paid resources | Not purchased | S2 must propose a compliant design without silently adding a service |
| DNS/domain purchase / transactional email / OIDC / paid AI / embeddings / OCR | Excluded | Not purchased | No activation or DNS execution authorized |
| Egress | No added charge assumed only within included EU allowance | EUR0 conditional | Actual allowance/usage/overage and restrictive egress design must be verified; alerts do not stop traffic |
| Teardown | No separate deletion fee established; accrued resources bill until actually removed | Unpriced residual exposure | Verify final account terms, rounded hours, IP persistence and any retained copies; reserve headroom and stop new spending before ceiling |

**Published-rate subtotal:** EUR79.8636 net. **Illustration only at 19% VAT:** EUR95.04 gross (EUR15.17 tax after rounding). Actual VAT is based on billing residence/status, not nbg1, and is **NOT VERIFIED**. The 720-hour calculation without monthly caps is EUR80.784 net / EUR96.13 gross at illustrative 19%; this is a planning allowance, not a promise about a live invoice. One further rounded hourly unit at that illustrative tax would be about EUR0.14; use a prudent teardown reserve instead of consuming all ceiling headroom.

At illustrative 19%, the capped model leaves about EUR54.96 of the EUR150 ceiling unallocated. That reserve authorizes no additional service. Any tax/rounding/egress/tail charges are included in the aggregate ceiling, not added above it. If the confirmed quote cannot fit, or a necessary volume/instance/service falls outside this exact list, STOP and obtain revised owner scope/budget approval; do not silently spend the reserve on extra resources.

The ceiling is an **owner authorization constraint**, not a provider-native hard stop. Future named-operator controls require all accrued/forecast charges and VAT reviewed daily, budget alerts, conservative stop-before-ceiling and timely teardown. A powered-off VM still bills; separately allocated IPs and any later separately approved volumes/copies must be accounted for. No alerts, account settings or teardown jobs are configured here.

## Capacity and recovery feasibility — OPEN

H05 plans 8 vCPU/16 GiB and **at least 100 GiB free after images**, plus dataset growth/consistent backup/restore scratch. Advertised GB is not proof of guest GiB or usable RAM. A 320 decimal-GB disk is approximately **298 GiB** before filesystem overhead. Reserving 100 GiB leaves approximately **198 GiB** for OS/images/data before extra growth/restore requirements.

This arithmetic is not qualification. Task 07's tiny synthetic sealed set and free-space observations are not a measured production-size footprint. No CPX42 host was ordered, mounted or benchmarked. Need exact loaded image/archive footprint, free space, PG/index/doc/log/definition growth and peak RSS/CPU/IO for Caddy/Next/API/worker/PG16/Redis/ClamAV/Chroma, then approved thresholds and cleanup/restore margins. No HA or dedicated-vCPU claim.

Extra restore VM, separate volume, cloud snapshot or off-host backup is outside the approved initial list. Independent new-target recovery and custody remain required gates; if they need excluded resources, obtain separate scope approval before implementing them. Do not waive backup/recovery gates to make a one-VM budget appear sufficient.

## Remaining decisions and next action

[Focused S2 preparation checklist](WAVE4_S2_SECURITY_ENTRY_CHECKLIST.md): every security, privacy, access, secret/key, Redis, recovery/retention/RPO/RTO, scanner, monitoring and deployment-entry acceptance remains OPEN. OD-BUDGET, H-REDIS-POLICY, OD-STAGING-LANGUAGES and all other owner decisions remain separate. No positive hosted journey or development-auth bypass is approved.

R1.0 remains **40/45** integrated. 00A/00B/07B/07C/08A remain open. PG-01 stays BLOCKED; PG-09 stays NOT STARTED; only historical PG-11 retains PASS; no PG/LG acceptance state changes or language activation. Hosted verification NOT RUN; human qualification OPEN.

Next action is review of this documentation PR, followed only upon separate instruction by S2-A security/design evidence preparation. No provisioning is authorized by this record, the future start time, merge or green CI.

## Documentation validation — 27 October 2026

Existing reconciliation/package/evidence regression tests: **117 passed**. Reconciliation: **452 items, zero unmapped**; package check: **45 packages**, acyclic dependencies and fresh generated documents; release-evidence check: valid/fresh, no unevidenced PASS. Ruff, four-shard plan (368 test files), product-positioning and release-matrix guards passed. Local link, 30-day interval, documentation-only diff and unchanged historical gate/language/evidence checks passed. An initial system-Python check could not read Python3.11 typing; rerun under the existing Python3.11 environment passed. Ruff was rerun successfully without cache after a cache-write permission failure. No dependencies installed. These local checks do not replace exact-head PR CI or hosted qualification.

## Public primary sources checked 27 October 2026

- [CPX42 official product resources](https://www.hetzner.com/cloud/regular-performance/)
- [Official new-order compute tariff](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
- [Anonymous nbg1 combined CPX42/IPv4 price catalog](https://website-price-api.hetzner.com/api/v1/products/CLOUD_128%2BCLOUD_21)
- [Primary IPv4 / free IPv6 pricing](https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/)
- [Networking/firewall product information](https://www.hetzner.com/cloud/)
- [Billing, caps, traffic and powered-off charges](https://docs.hetzner.com/cloud/billing/faq/)
- [Customer VAT rules](https://docs.hetzner.com/general/billing-and-account-management/billing-at-hetzner/value-added-tax/)
- [SKU/architecture and availability limitations](https://docs.hetzner.com/cloud/servers/faq/)
