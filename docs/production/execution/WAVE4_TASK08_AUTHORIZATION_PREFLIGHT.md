# Wave 4 Task 08 — hosted staging authorization and readiness preflight

**READY FOR OWNER DECISION — NOT READY TO DEPLOY.** Status date: 27 October 2026. This documentation task authorizes preparation only. No cloud provisioning, hosted deployment, registry publication, paid AI, real email/OIDC, real/original database migration, language activation, approval marker, PG/LG acceptance or automatic merge is performed or authorized. Wave 4 Task 08 is not roadmap package 08A (final release freeze/go-no-go). Full owner-approved S1 scope and the seven R1.0 languages remain unchanged; an unmet mandatory gate moves the date, not the scope.

## 1. VERIFIED baseline and Task 07 closure

Main `b463cf9b92b44a600c7b0e842574e1eb32e5e713` merges PR #273; reviewed PR source `a7fbec43fb2e2e54331655f44cac51065a43ae50`. All seven required **post-merge main push** workflows completed SUCCESS; S0 is VERIFIED. Task 07: **OFFLINE QUALIFIED — MERGED**. Tasks 01–07 completed their intended PR-head offline engineering; this is not hosted/human/production acceptance.

| Main workflow | Run / conclusion |
|---|---|
| Redis shared limiter regression | [40532405846](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532405846) — VERIFIED SUCCESS |
| AI budget governor qualification | [40532406230](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406230) — VERIFIED SUCCESS |
| Agent durable admission regression | [40532406060](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406060) — VERIFIED SUCCESS |
| Staging migration image regression | [40532406024](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406024) — VERIFIED SUCCESS |
| Encrypted recovery qualification | [40532406156](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406156) — VERIFIED SUCCESS |
| CI | [40532406132](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406132) — VERIFIED SUCCESS |
| Immutable local release regression | [40532406623](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40532406623) — VERIFIED SUCCESS |

The actual main-SHA connected artifact confirms **29 PASS / 0 FAIL / 0 SKIP / 6 NOT RUN**, not an inference from the old PR head. Original failed **27/2/6** and every earlier attempt remain unchanged in [Task 07 evidence](evidence/WAVE4_TASK07_INTEGRATION.json). PR-head backend **8,726 passed / 181 skipped**, frontend **1,561 passed**, primary Browser **672 passed / 14 skipped** plus **50 History repetitions** and all eight PR workflows are historical source-bound `a7fbec43` results. No main-SHA primary Browser run is claimed: that workflow is PR/on-demand. Main CI and the main image/CSP/connected workflows are separately verified above.

Current source-bound evidence: [Task 08 baseline record](evidence/WAVE4_TASK08_PREFLIGHT.json), [Task 07 report](WAVE4_TASK07_INTEGRATION.md), [audit](WAVE4_TASK07_INTEGRATION_AUDIT.md), [dashboard](PROJECT_STATUS_DASHBOARD.md), [release tracker](RELEASE_READINESS_TRACKER.md). No hosted target/account/service was inspected, reached or changed; hosted prerequisites below are OPEN/NOT RUN, not assumed absent or present in the owner's cloud account.

Preservation: 49 pre-existing worktrees (31 with local changes), 316 original branch tips and 203 protected/untracked file hashes recorded before this branch. A new isolated documentation worktree leaves all existing checkouts intact. Private inventory remains outside Git; no database/env/secret contents are published. Original SQLite is untouched, last observed 0027; no new SQL inspection or upgrade. No reset, clean, force push, worktree deletion or broad Docker cleanup.

## 2. Decision matrix and recommended architecture

**OPEN:** provider, region, operators, spending and execution authorization. The [complete owner packet](WAVE4_TASK08_OWNER_DECISIONS.md) contains 26 detailed decisions with all required evidence, risk, cost, owner, acceptance and deployment-versus-live blockers; the exact OD-BUDGET worksheet; every one of 37 unchanged Redis buckets; and all 104 unresolved rows carried from the owner register (including dated historical/future items, not silently reclassified as staging blockers).

**PROPOSED architecture pattern:** retain the existing Compose system on one isolated EU-region Linux x86_64 VM for the first controlled rehearsal, private to named testers. Caddy serves matching Next.js and API sibling domains; private PostgreSQL16, internal authenticated standalone Redis, ClamAV and shared private document/knowledge/index volumes stay off public ports. API, worker and one-shot migration share one verified backend; frontend has the same reviewed release and the approved API origin baked at build. Start one API/worker and explicitly authorize a 2/2 fault drill; Task 07 qualified 2/2 on one host, not multi-host scaling or HA. Nothing is deployed here.

Planning capacity only: 8 vCPU/16 GiB, at least 100 GiB free after images plus data/growth/snapshot/restore scratch space. This is an engineering starting envelope, not a measured minimum/SLO or approved purchase. Measure clamd/Next/PG/Chroma and job peaks under the owner's workload before resizing/acceptance. A single host is one failure domain. No Kubernetes, separate serverless frontend, distributed Chroma filesystem or replacement application architecture is proposed.

| Feasible option — all PROPOSED, selection OPEN | Fit and trade-off | Evidence / decision still needed |
|---|---|---|
| Hetzner EU VM (Germany/Finland) + independently controlled EU backup/key storage | Closest to current Compose and inexpensive published compute example; operator owns PG/Redis patching, backup, secret delivery, monitoring and incident response. No HA or managed-key feature assumed. | Published EU cloud tariff [H1]; actual x86 SKU availability, storage encryption/secret service/access/contract/support and complete quote unverified. |
| Scaleway Paris/Amsterdam VM; optional managed PG/Redis only after compatibility review | Same Compose app initially; regional storage/Secret Manager options reduce external vendor count. Managed database can reduce maintenance but changes backup privileges/network/hold behavior and requires fresh host qualification; no architecture rewrite needed for VM path. | Instance/storage pricing [S1/S2], regional availability [S3], Secret Manager [S4]. Service SKU/version/network/IAM/DPA/contract and approved quote still OPEN. |
| AWS Frankfurt EC2 + separately approved storage/secrets, optionally RDS PG16/private standalone-compatible Redis | Feasible EU compute region with broader managed building blocks; more IAM/network/cost and backup-copy complexity. Do not assume managed failover, custom recovery-GUC/locking privileges or Redis cluster compatibility. | Frankfurt region and EC2 availability [A1/A2]; region-specific itemized calculator estimate [A3] and provider/legal/ops review required. No numerical AWS total asserted. |

EU region is the proposed default; it is not an owner-approved jurisdiction or proof that model providers, support, logs, backups and subprocessors process data only in the EU. Privacy/legal qualifiers must review actual flows, contracts and locations. Off-host encrypted backup sets, independently controlled latest erasure ledger/head and separate key custody are required design elements; no cloud upload adapter currently follows from the local transfer simulator.

### Infrastructure cost assumptions — PROPOSED, not a quote or spend approval

Sources checked 27 October 2026, public pre-tax rates, no discounts/free credits assumed. H1 publishes a CX43 EU new-order tariff of **EUR15.99/month excluding IPv4/VAT**; it is a compute-only example, not a fully managed comparable or capacity certification. Re-quote SKU/availability at S1. S1 lists Paris BASIC3-X8C-16G at **EUR0.17768/hour** (about EUR129.71 for 730 hours). They are different performance/service products; equal CPU labels are not equal measured performance.

Illustrative Scaleway line-item scenario, chosen only to expose arithmetic: 730 VM hours; 200 GB additional 5K block storage at EUR0.000130/GB-hour; **100 GB TOTAL average retained encrypted objects**, not 100 GB per backup, at EUR0.01606/GB-month multi-AZ. Rounded lines: compute EUR129.71 + block EUR18.98 + objects EUR1.61 = **about EUR150.30/month before all exclusions**. This is not the approved budget or a complete bill. Dataset occupancy, retention/backup cadence and repeated full sealed sets can exceed the example substantially; 1,000 GB retained objects alone is EUR16.06/month at that rate. A 35-day retention proposal does not imply 100 GB stored. Storage sources S2; no claim that provider-native snapshots satisfy the application sealed-set/erasure requirements.

| Cost category | Unit/assumption and current status |
|---|---|
| Compute/API/workers/PG/Redis/clamd/Next | Example above only; actual capacity/replicas/managed options and HA quote OPEN. CI build minutes and any separate build host must also be budgeted. |
| Persistent SSD / restore scratch / snapshots | GB-month, IOPS and snapshot GB; 200 GB example is extra block capacity, not measured occupancy or an all-storage-inclusive SKU. Separate recovery scratch may double required free capacity. |
| Off-host backup / versions / ledger / key custody | Retained GB-month + copy/restore/egress + independent account/store/key access; full retention inventory and destruction/escrow costs OPEN. |
| Network / IPv4 / DNS / edge | IP, domain, egress/inter-region/NAT/VPN/firewall and certificate operation costs OPEN. ACME network/DNS activity needs later scope approval. |
| Secret manager / telemetry / registry | Secret/version/access, metrics/log ingestion and retention, paging, optional registry scans/storage/egress; vendor and amounts OPEN. No registry needed for qualified local offline transfer. |
| People / support / legal / native review | Operator/on-call/incident response, independent security/AI/native/licensing/legal qualifications; no staff or fees appointed. |
| Tax / currency / contingency | Owner obtains current quote, tax treatment and contingency; infrastructure EUR estimates do not authorize USD-only AI ledger spending. |
| AI / embeddings / email / identity | NOT RUN/OFF; separately authorized vendors/ceilings and purposes at S5; no inherited demo allowance or implicit free/unlimited credit. |

## 3. Safety, recovery and language decisions

**VERIFIED code; hosted evidence NOT RUN.** Retain non-root images, exact 11-tool registry and default-deny authorization; owner scoping and safe SSE; nonce CSP; exact CORS/trusted proxy controls; durable cross-instance admission and actual usage settlement; closed budget when approval missing; all disabled features, billing and Russian exclusion. Redis cannot replace PG locks/admission or monetary accounting. All 37 current failure policies remain local; class-specific deny/local proposals and availability consequences are in the owner packet, not runtime changes.

Recovery remains encrypted/sealed, independently anchored and new-target-only. Both application/checkpoint tables must share the PG16 public schema for the qualified path; no separate unbacked checkpoint URL. Source writers fenced/drained; all table/file/index hashes and current erasure ledger reconciled; provider snapshots/versions/replicas are inventoried separately. Sealed manifest authentication derives from the sealing key: do not promise an independently controlled cryptographic signing key where the present sealed format derives it. Ledger key/latest trusted head and SECRET_STORE_MASTER_KEY are separate custody items. Thirty-five-day retention/erasure values are engineering defaults awaiting counsel/owner; RPO/RTO are unset. Local restore seconds are not approved service targets.

No restored hold is released. Hold remains through verification and unknown usage/accounting/erasure reconciliation, with named approval, physical source/target identity and current ledger/receipt evidence. Any future authorized hold change requires connection recycling; AI kill remains until separate budget/resume authority. Any failure retains quarantine. No data, reservation or unknown charge is discarded to allow rollback.

### OD-STAGING-LANGUAGES — two paths, neither approved

| Path | Technical/data/legal and schedule consequence | Status and acceptance boundary |
|---|---|---|
| A: explicitly authorized isolated development-class synthetic exercise | Named testers, synthetic/licensed data, separate account/network/credentials and no real candidate data. Existing development identity fallback must never be exposed as hosted authentication; a safe harness/access plan and any required focused code review precede use. No hosted activation override or copied production secret. Paid provider use still separately requires OD-BUDGET. It can shorten infrastructure/test discovery while human review continues. | PROPOSED / OPEN. It proves only the declared synthetic/development scope. It does not pass hosted PG-06 or human LG gates, authorize a real-user beta or waive seven-language S1 scope. No such hosted exercise is created here. |
| B: qualify an initial locale through all LG-01–LG-14, then permit hosted Candidate journeys | Native/legal/security/AI reviewers, source/market licences, approved datasets/providers/thresholds and release-bound records required. Owner names test locale; English is not pre-approved. Remaining six languages remain full R1.0 obligations. Longer calendar path depends on independent reviewer availability and legitimate evidence. | OPEN / BLOCKED. Current strict-hosted registration/activity refuses every unqualified locale. A bootstrap gap exists where a protocol needs a positive hosted journey before activation: security/product/legal reviewers must approve an evidence path/qualification mechanism in a separate reviewed scope, without claiming path A alone satisfies hosted requirements or inserting fake approval records. No generic API_ENV bypass resolves it. |

PROPOSED decision: keep strict staging closed and conduct safe refusal/infrastructure qualification only; owner ratifies the language qualification protocol and appoints reviewers before any positive hosted journey. Approve record expiry and actual release-SHA ancestry checks under OD-APPROVED-UNTIL; do not fabricate approved_until or a signature. No language activation file is changed.

## 4. 07B / 07C and independent human prerequisites

| Package | Evidence already VERIFIED | Missing prerequisites and bounded acceptance plan — OPEN / NOT RUN |
|---|---|---|
| 07B grounding and agent-policy | Merged preflight/RAGAS audit and deterministic policy/registry/authorization/security checks. Historical zero relevancy/recall cause unresolved. | First diagnose historical scoring/data/run alignment; owner-approved synthetic/public licensed corpus and markets, independent held-out author and at least protocol-required independent raters, frozen prompts/model/provider routing/embedder/index/corpus/evaluator hashes, spend/request/token/concurrency ceilings and pricing expiry. Preapprove per-language/market grounding/citation/retrieval/tool-use/benign-FP/attack thresholds and sample/rubric before evaluation. Record denominators, abstentions, provider failures, actual/unknown usage and uncertainty; RAGAS is secondary to independent human ratings. S5 paid/source/language authority and hosted observability precede live runs. No run/dataset creation here. |
| 07C OCR/documents | 14 local synthetic image/PDF OCR observations across seven locales; real offline documents/ownership/clamd/refusal path. | Approve synthetic/licensed multilingual PDF/image set and reference transcription, source/data licence/retention and per-language native adjudication; freeze OCR engine/language packs/versions/config and file hashes. Owner approves accuracy/error/injection/scanner/timeout thresholds, sample sizes and resource bounds. Run real hosted ingest/OCR/ownership/scanner/unsafe-file/refusal and independent quality protocol later. Local OCR need not be paid, but selected external OCR/embedding/AI cannot inherit approval. No CV/private candidate data, no unapproved dataset or evaluation here. |

For either: owner-approved pass/fail thresholds are unset, so no numeric cutoff is invented. Any failed mandatory safety, quality, privacy or accounting criterion stops qualification, preserves source-bound failed evidence, fences paid activity and raises a focused remediation PR. Re-run only under an approved frozen protocol; do not retune held-out cases or suppress failures to manufacture PASS.

### Reviewer and appointment matrix — all names UNASSIGNED / OPEN

| Required role | Accountable appointment / evidence deliverable |
|---|---|
| Platform/operations lead + backup | Owner names provision/deploy operator, least-privilege access, patch/storage/secret/rehearsal duties and schedule; no grant in this packet. |
| Security reviewer independent of author | Threat/permission/CSP/proxy/injection review, hosted access/network and negative results; signed release-scoped report. |
| Independent AI-quality evaluators | Frozen blinded protocol, at least three raters where required by existing 06G pack, per-language ratings/sample sizes/agreement; not replaced by deterministic scores. |
| Native English reviewer | Owner names independent en qualifier, frozen catalogue/flows, defects and LG-11 sign-off. |
| Native German reviewer | Same deliverable for de; separate named language competence/evidence. |
| Native Spanish reviewer | Same for es. |
| Native Italian reviewer | Same for it. |
| Native Portuguese reviewer | Same for pt, explicitly approved language/market variety. |
| Native French reviewer | Same for fr. |
| Native Dutch reviewer | Same for nl. |
| Legal/privacy qualifier(s) | Qualified advice on data handling, notices/translations per language, jurisdictions, vendor terms, retention/erasure and disclosures; no legal judgment by this packet. |
| Content/licensing reviewer | Source/version/licence/market authority, permitted retention/processing and citations. |
| Key/erasure-ledger custodian + reconciliation owner | Independent current heads/keys, receipts and preserved unknown accounting; dual review and escrow procedure. |
| Incident-response owner/commander + on-call backup | Incident severity/contact/ack/escalation/fencing/recovery acceptance and rehearsal. |
| Product acceptance owner | S1 coverage, threshold/rubric/product-policy disposition and real journey acceptance. |
| Release authorization owner | Final evidence SHA, 08A freeze/go-no-go and separate deployment/rollback permissions. |

Appointments need names, authority boundaries, conflicts/independence, access, start/due dates, backup and deliverable/sign-off references. Nothing in the named role list appoints a person. Full S1 timeline depends on this capacity; the November target cannot reduce obligations.

## 5. Full 45-package roadmap snapshot and five layers

VERIFIED IDs/names from `execution_packages.PACKAGES`; integration count retained **40/45**. Integrated engineering is distinct from global offline CI, hosted staging, human qualification and gate acceptance. Baseline main CI is green globally; it is not a new per-package acceptance approval. The earlier generated register retains its dated per-package implementation history. Cross-cutting Tasks01–07 are engineering follow-ups, not five additional completed packages.

| ID | Package | Engineering | Offline CI | Hosted staging | Human qualification | Gate acceptance |
|---|---|---|---|---|---|---|
| 00A | Governance, reviewers and owner decisions | OPEN — partial governance | VERIFIED baseline global suite | n/a | Owner names reviewers, counsel and legal qualifiers (OPEN) | PG-07 BLOCKED until reviewers are named |
| 00B | Scope reconciliation delta (documentation only) | OPEN — owner proposal disposition | VERIFIED baseline global suite | n/a | Owner disposition of the ten reclassifications (OPEN) | PG-11 PASS (machine-checked); no reclassification applied |
| 01A | Prompt-injection corpus, risk score and quarantine (REVIEW-01 part 1) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (injection screen on hosted stack) | Human security review (9 questions); independent held-out author (OPEN) | PG-03 IN PROGRESS; thresholds unapproved (OD-GATE-THRESHOLDS) |
| 01D | Tool-call authorization layer (REVIEW-01 part 2) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | Security review of tool authorization | PG-03 (REVIEW-01 R4/R5) |
| 01B0 | Prompt asset format and loader contract (interface package) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-12 IN PROGRESS |
| 01B | Externalized, versioned prompts (REVIEW-02) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted prompt rollback/refusal; local image assets verified in Wave 4 Task 03) | NONE REQUIRED for engineering; release qualification separate | PG-12 IN PROGRESS (01C and 01D merged; acceptance evidence still required) |
| 01C | Tool registry parity (REVIEW-03) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-12 (REVIEW-03) |
| 02K | Knowledge runtime and manifest contract (interface package) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-05 IN PROGRESS (contract) |
| 02A | Permanent Knowledge reliability: persistence, environment identity, restore (REQ-OWN-05) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted volumes, PostgreSQL, multi-worker; OD-HOSTED) | NONE REQUIRED for engineering; release qualification separate | PG-05 IN PROGRESS |
| 02B | Embedding integrity and index manifests (REVIEW-04) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (production embedder, hosted refusal; OD-HOSTED, OD-EMBED) | Embedder choice and benchmark approval (OD-EMBED, OD-BUDGET) | PG-05 NOT MET (retrieval quality unmeasured) |
| 02C | Real malware scanning for uploads | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (real clamd, EICAR, outage drill; OD-HOSTED) | NONE REQUIRED for engineering; release qualification separate | PG-05 IN PROGRESS |
| 02D | Market source qualification and licensing (selected EU markets) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | Licensing reviewer and owner; per-market signed approval (OPEN, long lead) | PG-05 (licence and market qualification) |
| 02E | Retrieval quality and the frozen beta-scope coverage measure | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN | Frozen coverage measure approval (OD-COVERAGE); independent datasets | PG-05 (retrieval quality, coverage) |
| 03A | Admin navigation foundation (REQ-OWN-08) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live Admin walkthrough) | NONE REQUIRED for engineering; release qualification separate | PG-08 IN PROGRESS |
| 03B | Admin Plans: Basic/Premium management (REQ-OWN-02) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live Admin walkthrough) | Plan limit values (OD-PLAN-LIMITS) | PG-08 IN PROGRESS |
| 03C | Admin Users: complete user management (REQ-OWN-03) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live Admin walkthrough) | Bulk-action policy (OD-BULK-ACTIONS) | PG-08 IN PROGRESS |
| 03K | Admin metric and report contract (interface package) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-14 IN PROGRESS (contract) |
| 03D1 | Command Center metrics and AI operations read model (REQ-OWN-01, backend) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live data) | NONE REQUIRED for engineering; release qualification separate | PG-08 IN PROGRESS (views merged; staging outstanding) |
| 03D2 | Command Center and AI operations views (REQ-OWN-01, frontend) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN | NONE REQUIRED for engineering; release qualification separate | PG-08 |
| 03E1 | Reports registry, governed builder, saved configurations and exports (REQ-OWN-04, backend) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live data) | Export formats (OD-REPORT-EXPORT) | PG-14 IN PROGRESS (views merged; staging outstanding) |
| 03E2 | Reports catalogue, builder and export views (REQ-OWN-04, frontend) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN | Export formats (OD-REPORT-EXPORT) | PG-14 |
| 04A | Story Bank completion (REQ-OWN-06) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (restart on staging) | Native review of 116 strings (LG-10/11) | PG-13 IN PROGRESS (06B merged; staging and human review outstanding) |
| 04B | Workspaces completion (REQ-OWN-07) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (PostgreSQL invitation race and row locks) | Transfer rules (OD-WS-TRANSFER); native review | PG-13 IN PROGRESS (06B merged; staging and human review outstanding) |
| 04C | Agent streaming and cancellation (REVIEW-05) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (streaming on staging) | NONE REQUIRED for engineering; release qualification separate | PG-06 |
| 04D | Candidate journey reliability (REQ-CAND-01) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (journeys on a staging stack) | NONE REQUIRED for engineering; release qualification separate | PG-06 |
| 04E | Invitation-only registration (REQ-BETA-01) | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (first-admin bootstrap, live Google) | Invitation email and issuer decisions (OPEN) | PG-02 IN PROGRESS (05D merged; live verification outstanding) |
| 04F | Browser dictation disclosure and verification | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (browser dictation check) | Legal reviewer and test participants | PG-04 |
| 05A | Hosted topology and platform hardening | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (nothing deployed; OD-HOSTED) | Hosting authorisation (OPEN) | PG-01 BLOCKED |
| 05B | Persistence, backup, restore and rollback drills | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted/off-host recovery and custody; Task 06 disposable PostgreSQL qualification; OD-HOSTED) | Recovery/custody/retention owners and legal approval OPEN | PG-09 NOT ACCEPTED; engineering evidence does not approve RTO/RPO |
| 05C | Observability, alerting and provider resilience | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted budget/outage/recovery; OD-HOSTED; Task 05 disposable qualification, no hosted approval) | AI budget (OD-BUDGET) | PG-09 |
| 05D | Identity, email and rate limiting live | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted Brevo, Google, Redis; OD-HOSTED; disposable Redis qualified in Task 04) | NONE REQUIRED for engineering; release qualification separate | PG-02 |
| 05E | Privacy, legal and data-rights readiness | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | Legal counsel sign-off per offered language (long lead) | PG-04 |
| 06A | Locale audit and language boundaries | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | Native review of the audit baseline | PG-10 IN PROGRESS; LG-01 and LG-14 evidence exists, none approved by a named human |
| 06B | Per-language journeys, Story Bank and Workspaces | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (journeys per language) | Native-speaker review | LG-03, LG-09 per language; PG-13 |
| 06C | Per-language AI behaviour: prompts, interview and feedback | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live Mo quality) | Blinded native-reader rating (OD-BUDGET) | LG-04, LG-05 per language |
| 06D | Multilingual retrieval and cross-language attribution | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (production embedder; OD-EMBED) | Sample review | LG-06 per language |
| 06E | Per-language injection, security and privacy suites | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN | NONE REQUIRED for engineering; release qualification separate | LG-08 per language; PG-03 |
| 06F | Native review and legal translation qualification | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | Seven native reviewers and legal qualifiers (calendar-bound, OPEN) | LG-10, LG-11 per language; PG-04 |
| 06G | Independent human AI evaluation | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (live Mo outputs) | Independent reviewers and participants (OD-BUDGET, OD-GATE-THRESHOLDS) | PG-07 BLOCKED |
| 06H | Language activation control: fail-closed enforcement of LG-01 to LG-14 before real-user activation | VERIFIED — integrated engineering | VERIFIED baseline global suite | NOT RUN (hosted fail-closed behaviour) | Approvers named for each gate (OD-LANG-03/04) | PG-10 IN PROGRESS; LG-13/LG-14 enforcement merged, zero languages qualified |
| 07A | Deferral inaccessibility and engineering hygiene | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-10 |
| 07B | Live grounding and agent-policy validation | NOT RUN — live residual | VERIFIED baseline global suite | NOT RUN (live grounding; OD-BUDGET) | NONE REQUIRED for engineering; release qualification separate | PG-03 |
| 07C | Residual live verifications | NOT RUN — hosted/independent residual | VERIFIED baseline global suite | NOT RUN (local synthetic OCR measured; hosted quality NOT VERIFIED) | NONE REQUIRED for engineering; release qualification separate | residual live verification |
| 08A0 | Release evidence pipeline (continuous integration of evidence) | VERIFIED — integrated engineering | VERIFIED baseline global suite | n/a | NONE REQUIRED for engineering; release qualification separate | PG-15 (evidence pipeline) |
| 08A | Freeze and owner go/no-go | BLOCKED — final freeze/go-no-go | VERIFIED baseline global suite | NOT RUN | Owner go/no-go | PG-15 |

No package is promoted solely because this preflight or Task 07 merged. Open package plans: 00A appointments/decisions; 00B explicit item-level owner disposition without applying the ten reclassification proposals; 07B/07C prerequisites above; 08A only after mandatory evidence and separate release authority. Existing source, market, product and privacy requirements remain in scope.

## 6. Production-gate gap matrix — acceptance states retained

The release evidence ledger/tracker, rather than dated 21 October matrix descriptions, supplies current acceptance-workflow state. The acceptance matrix still defines the required evidence. VERIFIED offline engineering below never converts to a production PASS.

| Gate | Retained state | Available evidence | Missing evidence / owner / next checkpoint |
|---|---|---|---|
| PG-01 | BLOCKED | VERIFIED offline: Immutable/nonce-CSP/Compose/connected main CI | OPEN / NOT RUN: Hosted access/TLS/storage/secrets and rehearsal; operations/owner; S1-S4/S6 |
| PG-02 | IN PROGRESS | VERIFIED offline: Invitation, real synthetic sessions/expiry/logout and isolation | OPEN / NOT RUN: Authorized email/recovery/OIDC-or-disabled rounds and lifecycle; security; S5/S6 |
| PG-03 | IN PROGRESS | VERIFIED offline: Allowlisted parity/authorization, quarantine and multilingual offline injection tests | OPEN / NOT RUN: Independent frozen held-out safety/FP thresholds and hosted review; AI safety/security/owner; S5-S7 |
| PG-04 | NOT STARTED | VERIFIED offline: Privacy/erasure/legal review packs, conservative data controls | OPEN / NOT RUN: Qualified counsel/native legal texts, provider/retention/data-rights evidence; legal; S2/S7 |
| PG-05 | IN PROGRESS | VERIFIED offline: Persistence/manifests/hash refusal/scanner/EICAR/empty-index recovery | OPEN / NOT RUN: Approved populated semantic corpus, provider/index/market licences and host source restore; knowledge/licensing; S5/S6 |
| PG-06 | NOT STARTED | VERIFIED offline: Actual offline Caddy/browser/SSE/Stop/same-API recovery and usage safety | OPEN / NOT RUN: Per-language real hosted Candidate/Practice journeys and approved latency/availability; product; S5-S7 |
| PG-07 | BLOCKED | VERIFIED offline: Blinded protocol/review sheets exist | OPEN / NOT RUN: Named independent human raters and signed sample/agreement results; quality/owner; S7 |
| PG-08 | IN PROGRESS | VERIFIED offline: Admin permission/aggregate/privacy/UI CI | OPEN / NOT RUN: Hosted walkthrough and unresolved plan/bulk/product-policy approval; product/security; S6/S7 |
| PG-09 | NOT STARTED | VERIFIED offline: Encrypted PG16 transfer/erasure/held restore; incompatible rollback refusal | OPEN / NOT RUN: Off-host/key custody/retention/RTO/RPO/alert/host recovery and authorized reconciliation drills; operations; S2/S6 |
| PG-10 | IN PROGRESS | VERIFIED offline: Disabled feature/inaccessibility/billing/Russian boundary suites | OPEN / NOT RUN: Release-bound independent acceptance; no enablement by preflight; release/security; S7 |
| PG-11 | PASS | VERIFIED offline: 452 issues/zero unmapped; historical outcomes retained | OPEN / NOT RUN: Re-run checker on this PR; existing machine PASS only, no new approval; owner/engineering; S0/S7 |
| PG-12 | IN PROGRESS | VERIFIED offline: Prompt version/hash/rollback and exact11-tool registry parity; image attribution | OPEN / NOT RUN: Named acceptance and real release/prompt rollback provenance; AI platform/release; S3/S6/S7 |
| PG-13 | IN PROGRESS | VERIFIED offline: Story/Workspace ownership/revoke/persistence engineering | OPEN / NOT RUN: Seven-language real hosted restart/revoke and native/product acceptance; collaboration lead; S6/S7 |
| PG-14 | IN PROGRESS | VERIFIED offline: Governed aggregate/report/CSV/JSON/PDF and suppression tests | OPEN / NOT RUN: Hosted authorized export/privacy walkthrough and export/product acceptance; product; S6/S7 |
| PG-15 | NOT STARTED | VERIFIED offline: Evidence pipeline and invitation/free-beta boundaries | OPEN / NOT RUN: All mandatory gate evidence, support/on-call, full-scope freeze and owner go/no-go; release owner; S8 |

### LG-01–LG-14 per language — no approvals

Codes: **D = OPEN, ENGINEERING DRAFT only** in acceptance ledger; **N = NOT RUN**; **O = OPEN, NOT STARTED**. None means approved/PASS. Raw engineering `language_readiness.json` says PASS for LG-01/LG-14, but the acceptance ledger deliberately treats those as drafts without named human/release approval; do not misreport them as approved gates. All seven languages currently have 0/14 accepted gates, production_qualified=false and offered_to_real_users=false. Russian remains excluded.

| Gate / missing approval evidence | en | de | es | it | pt | fr | nl |
|---|---|---|---|---|---|---|---|
| LG-01 — Locale audit: release-bound approved inventory | D | D | D | D | D | D | D |
| LG-02 — Interface: native complete text and leak review | D | D | D | D | D | D | D |
| LG-03 — Candidate journeys: approved realistic per-language run | N | N | N | N | N | N | N |
| LG-04 — Prompts/policies: frozen live and independent verification | N | N | N | N | N | N | N |
| LG-05 — Interview quality: blinded human rubric/sample | O | O | O | O | O | O | O |
| LG-06 — RAG: approved per-market retrieval/citation benchmark | O | O | O | O | O | O | O |
| LG-07 — Country separation: native/market-reviewed evidence | D | D | D | D | D | D | D |
| LG-08 — Security/privacy: independent multilingual held-out protocol | O | O | O | O | O | O | O |
| LG-09 — Story/Workspace: restart/revoke real locale journeys | N | N | N | N | N | N | N |
| LG-10 — Legal/privacy translation: qualified sign-off | O | O | O | O | O | O | O |
| LG-11 — Native human review: named reviewer/sign-off | O | O | O | O | O | O | O |
| LG-12 — Mo language ownership: live/human consistency | D | D | D | D | D | D | D |
| LG-13 — Readiness records: complete dated approver/release references | D | D | D | D | D | D | D |
| LG-14 — Boundaries: current release and Russian/disabled controls acceptance | D | D | D | D | D | D | D |

These are separate cells for each locale; shared offline tooling is not a shared human sign-off. Source/market licences, provider routing/pricing, date/number/error display, consent/disclosure and review independence must be evidenced for the actual offered locale, never inferred from English or an aggregate score.

## 7. Dependency-ordered staging plan — NO STAGE EXECUTION AUTHORIZED

| Gate / state now | Objective evidence / dependencies | Accountable owner / exact further approval | Stop / rollback criteria |
|---|---|---|---|
| S0 VERIFIED | PR273 merged; all seven main-push runs SUCCESS at b463cf9b; actual main offline campaign29/0/6. | Engineering records evidence; owner review of this packet/PR still pending. | Any new mandatory failure/material main change invalidates baseline; investigate before implementation. |
| S1 OPEN / deployment BLOCKED | H01/H02/G01: chosen provider/account/region, named infrastructure operator, project isolation, full quote, currency/ceiling/expiry and synthetic-only data scope. | Owner WRITTEN approval to provision only the specified staging resources and later operations; approval of packet/proposal alone is insufficient. | No billable creation until approved; overrun/expiry/access mismatch stops activity; teardown authority and data-preservation owner defined. |
| S2 BLOCKED on S1 | Approved network/secret/key/storage/backup/retention/access/monitoring design, owner-approved RPO/RTO, privacy/vendor review, independent ledger head and operator roles. | Security/privacy/operations review; owner authorizes exact infrastructure configuration and secret delivery, with no provider/AI/email activation. | Unexpected ingress/egress, exposed secrets/private paths, absent custody/retention or failed controls stops rollout; isolate, preserve evidence. |
| S3 BLOCKED on S1/S2 | Reviewed release/domain SHA, application/web/operator image identities and canonical manifests; approved offline archive transport or separately reviewed registry design; current target inventory and one-shot0048 plan. | Release owner approves bundle/anchors, named empty staging target and exact migration operation; database operator approval separate from original dev DB. | Wrong hash/platform/API origin/schema, unsupported dependency pin, unknown/held/unsettled state or stale drain observation refuses; forward-fix, no auto downgrade. |
| S4 NOT RUN / BLOCKED | S1-S3 authority; provision only approved target, approved zero-paid-call startup/migration/refusal tests: readiness, private volumes, DB/Redis, fresh scanner definitions, TLS/CSP, unauthorized auth/language/data/egress refusal, budget CLOSED. | Owner explicitly authorizes first staging deployment and named zero-paid-call test protocol. S1 approval alone must explicitly include this or another written approval is required. No external email/OIDC, model call or language activation. | Migrator must reach sole0048 once; failure stops API/worker. Pause/isolate on unsafe ready or unexpected egress; retain state/evidence; compatible image rollback only under S3/R06 authority. |
| S5 OPEN / NOT RUN | OD-BUDGET full approved config/marker/price/expiry and bounded purpose; service-specific email/IdP/provider/source/model/data licences; language qualification protocol. Not all services need activation. | Owner issues separate per-service/per-evaluation approval; supplies exact IdP/vendor inputs and controlled recipient/dataset scope. No blanket live-service authority. | Missing/expired/changed policy, price/model drift, unknown charge or data/security failure closes paid admission; preserve reservations and receipts; renew authority, never reset ledger. |
| S6 NOT RUN / BLOCKED | S4 plus applicable S5; real hosted multi-instance SSE/Stop/usage/Redis/PG/worker/scanner/storage/proxy and separate-target off-host encrypted erasure/hold recovery; source/prompt/image rollback; approved 07B/07C protocol. | Named operations/security/quality reviewers authorize fault/drill scope; separate authority before hold release or any production rollback. | Any mandatory failure blocks qualification; quarantine restored target, fence producers, retain unknowns/current erasure history; focused remediation and approved rerun. |
| S7 OPEN / BLOCKED | All mandatory PG/LG evidence, independent/native/legal/licensing ratings, unresolved00A/00B/product decisions and full45-package/five-layer record. | Named independent qualifiers sign their scopes; owner accepts release/locale records only with legitimate complete evidence. | Unmet mandatory gate or unreviewed market/language stays inactive; do not cut S1 scope to meet date. |
| S8 NOT RUN / BLOCKED | Separate roadmap08A freeze, reviewed release/evidence SHA, every mandatory gate, incident/support/beta operations and rollback/recovery readiness. | Owner's separate final go/no-go and production/deployment authorization. Wave4Task08 packet grants neither. | No-go on failed/missing evidence. Production rollback/restoration requires fresh incident/release authority; never automatic or a DB downgrade. |

### Future migration and rollback order (plan only)

1. Obtain explicit S1-S4 scope, resource/data/secret/expiry/spend authority; review physical target/database/checkpoint/volume identities. Do not inspect, migrate or import the original SQLite or any existing private environment.
2. Build once from the chosen reviewed SHA with the approved real API domain; verify API/worker/migrate identity, matching web, derived operator, migration0048, dependencies, prompt/activation hashes and trusted independent anchors. Do not deploy the Compose build template or use unreviewed overlays; local images are loaded/verified, never silently re-pulled.
3. On the separately authorized new target, fence producers, review a fresh drain/state observation and any required sealed backup; start private PG/Redis/clamd and storage only within authorized scope. Execute the one-shot migrator exactly once; assert sole0048; only then start API/worker and web/Caddy. No per-process startup migration, no automatic downgrade.
4. Verify every replica's readiness plus independently measured worker/scanner freshness and actual edge controls; readiness alone is not all operational acceptance. Observe with CLOSED AI, strict language refusal and explicit no-paid/provider egress. Keep no-real-candidate-data restriction until data/privacy/service authority exists.
5. If failure: fence admissions/writers and retain logs without private content. An image-only rollback omits migrate and requires compatible schema, previous qualified release, fresh drained target, no active/unsettled run, no recovery hold, budget capability2 and recovery1. A schema match is necessary, not sufficient for functional compatibility. Never remove reservations to make it pass.
6. If images are incompatible or usage uncertain, forward-fix or obtain a separate authorized new-target recovery. Preserve original source and independently current erasure/receipt history; reapply erasure and reconcile monetary unknowns. No in-place restore/overwrite; no automatic hold release or production rollback. Stop and get legitimate named incident/DB/release authority.

## 8. Precise owner authorizations needed before the first actual deployment

**OPEN:** provide a dated written record naming (1) provider, account/project, EU region and permissible data locations; (2) infrastructure lead/operator and authorized access; (3) exact resources/capacity/duration, currency, total spend ceiling/expiry and teardown/incident owner; (4) staging-only purpose, named testers, synthetic/licensed data and strict exclusion of original/private/production data; (5) domains/DNS/TLS/firewall/egress/secret delivery; (6) DB/checkpoint/storage/Redis/scanner configuration and per-class outage decisions; (7) encryption, signing/authentication, erasure-ledger/master-key custody, off-host backup, retention and RPO/RTO plan; (8) selected release SHA, real-domain build, trusted immutable bundle/transport and migration0048 target/one-shot operation; (9) named security/privacy/operations reviews, monitoring/alert/escalation; (10) explicit permission to execute ONLY the described zero-paid-call deployment and refusal tests at S4, with compatible rollback/isolation boundaries.

Leave paid AI, emails/OIDC, registry publication, positive unqualified-language journeys, real-user data, recovery-hold release and production operations excluded unless separately reviewed and expressly authorized. Missing values remain blank/OPEN in the decision packet; no key/marker/approval JSON is generated. **Prioritized next owner action:** appoint the operations lead and return the completed H01/H02 OD-HOSTED written decision with provider/region, capped infrastructure spend and exact staging scope. That is the prerequisite to secure-design review, not an automatic instruction to deploy.

## 9. Public evidence sources and assumptions

Checked 27 October 2026; publicly visible tariffs/capabilities, no account/checkout/signup or provisioning. Recommendations and derived cost arithmetic are engineering inferences, not vendor quotes or owner decisions. Recheck at procurement; no exchange-rate conversion or guarantee of capacity/availability. Jurisdiction/privacy adequacy and legal retention are left to qualified review.

- H1 [Hetzner official EU new-order tariff, effective15June2026](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) — CX43 EUR15.99, IPv4/VAT excluded; current SKU/shape/capacity quote required.
- S1 [Scaleway official instance prices](https://www.scaleway.com/en/pricing/virtual-instances/) — Paris BASIC3-X8C-16G EUR0.17768/hour, taxes excluded; billing basis and availability recheck.
- S2 [Scaleway official storage prices](https://www.scaleway.com/en/pricing/storage/) — 5K block EUR0.000130/GB-hour; multi-AZ objects EUR0.01606/GB-month, before tax; transfer, snapshots, versions/retention separately considered.
- S3 [Scaleway regional product availability](https://www.scaleway.com/en/product-availability-by-region/?categories=storage) — product/AZ availability is specific; region availability is not a purchase guarantee.
- S4 [Scaleway Secret Manager documentation](https://www.scaleway.com/en/docs/secret-manager/faq/) — region-scoped secret service; actual IAM/custody/deployment integration unqualified here.
- A1 [AWS region list](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html) — Frankfurt eu-central-1 is in Germany.
- A2 [AWS EC2 types by region](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-regions.html) — region/type selection requires current provider confirmation.
- A3 [AWS Pricing Calculator](https://calculator.aws/) — require a saved region-specific itemized estimate for compute/storage/DB/Redis/network/secrets/logs/backup/support before approval; no AWS price invented here.

Repository authorities: [owner register](../OWNER_DECISION_REGISTER.md), [acceptance criteria](../PRODUCTION_ACCEPTANCE_MATRIX.md), [backup runbook](../BACKUP_RESTORE_RUNBOOK.md), [qualified recovery](WAVE4_TASK06_RECOVERY.md), [release controls](WAVE4_TASK03_IMMUTABLE_RELEASE.md), [Redis decisions](WAVE4_TASK04_REDIS_DECISIONS.md), [budget specification](OD_BUDGET_SPECIFICATION_TASK05.md), [dated post265 plan](STAGING_READINESS_PLAN_POST265.md), [S1 roadmap](../PRODUCTION_MASTER_ROADMAP_V2.md). Older descriptions in these dated records are historical; this packet reconciles current offline engineering without manufacturing hosted acceptance.
