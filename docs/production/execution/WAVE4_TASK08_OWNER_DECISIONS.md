# Task 08 — owner-decision and authorization matrix

**H01/H02 APPROVED FOR S1 DOCUMENTATION ONLY — NOT READY TO PROVISION OR DEPLOY.** See [owner-approved S1 documentation record](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md) for the exact 27 October owner statement and approved fixed window. Overall OD-HOSTED and S1 deployment-entry remain PARTIAL / OPEN / BLOCKED; all other worksheet acceptances remain OPEN. Defaults remain PROPOSED. H/R/S/A/L/Q/G/I references are worksheet labels under existing IDs, not runtime approval markers. [Main packet](WAVE4_TASK08_AUTHORIZATION_PREFLIGHT.md).

Each card explicitly records required decision, proposal, available/missing evidence, accountable role, security/privacy consequence, cost, prerequisites, current authorization state, acceptance and blocking phase. H01/H02 now record only the named owner-approved terms below; no other appointment, spend scope or acceptance is inferred.

## H01 — Provider, account/project, region and permitted data locations

- **Decision ID:** OD-HOSTED. **Authorization:** OWNER-APPROVED FOR S1 DOCUMENTATION ONLY; overall hosting execution PARTIAL / OPEN.
- **Recorded selection:** Hetzner Cloud, Nuremberg nbg1, isolated ask4mo-staging-eu, one CPX42 x86 Linux VM with included 320 GB system disk, one primary IPv4, IPv6, one private network and firewall. Primary application/DB/documents/index/logs/runtime-secret processing Germany only. Future independently controlled encrypted backups Germany/France only after separate approval; cloud backup provisioning is excluded now.
- **Authority / exact text:** [owner-approved S1 documentation record](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md). Mo Al-Tamimi explicitly approves every stated field; no fallback SKU, region or additional service is authorized.
- **Evidence available:** Current main bf579aa5 and seven green post-merge workflows; official catalog/specifications and itemized rate model. **Still missing:** Account-specific stock/quota and billing-tax quote, measured usable disk/RAM/restore headroom, contract/DPA and all processing-location/access verification. Catalog active=true is not stock.
- **Acceptance boundary:** Owner selection is recorded; S1 resource/deployment-entry remains BLOCKED. No account creation, purchase, provisioning, DNS, registry or deployment authority. S2 security/privacy/recovery and later execution approvals remain independent.

## H02 — Infrastructure spend, duration, permitted operations and named operator

- **Decision ID:** OD-HOSTED / OD-RESOURCE. **Authorization:** OWNER-APPROVED FOR S1 DOCUMENTATION ONLY; execution NOT AUTHORIZED.
- **Recorded terms:** Mo Al-Tamimi accepts operations, billing and shutdown accountability and is the only authorized operator/tester. Aggregate ceiling EUR150 including applicable VAT and all authorized infrastructure charges; fixed interval 28 October 2026 09:00 CET through 27 November 2026 09:00 CET exclusive (30 days). No automatic shift, renewal, scaling or new billable services.
- **Permitted scope / exclusions:** Infrastructure-only preparation, security and synthetic offline qualification, subject to separate S2/entry approvals. Exact resource list and all owner exclusions in [owner-approved S1 documentation record](WAVE4_S1_H01_H02_OWNER_AUTHORIZATION.md); no paid AI/embeddings/OCR, real candidate data, transactional email/OIDC, languages/public beta/production/live billing, extra storage/instances, cloud backups, registry publication or budget increase.
- **Evidence / missing:** Exact written approval received 27 October; no separate signature time invented. Actual customer VAT/stock/quote and capacity NOT VERIFIED. Ceiling is an owner constraint, not provider-native hard enforcement. Operator must review charges, stop new spend before the ceiling and plan timely deletion only of separately authorized new rehearsal resources.
- **Acceptance boundary:** Named terms recorded, but no purchase/deployment authorization, monetary reset, hold release or specialist appointment. Wider OD-RESOURCE and OD-BUDGET remain OPEN. [S2 security/deployment-entry checklist](WAVE4_S2_SECURITY_ENTRY_CHECKLIST.md) remains entirely OPEN.

## H03 — PostgreSQL hosting and privileges

- **Decision ID:** OD-HOSTED. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** PostgreSQL hosting and privileges. PROPOSED PostgreSQL 16 on private network, app and official checkpoints in the SAME database/public schema; managed option only after compatibility review.
- **Evidence available:** 0048 migration, outage/admission and qualified recovery pass on disposable PG16. **Missing evidence:** Host encryption, patching, backup/PITR scope, restore privileges, snapshot/table-lock/custom recovery-GUC qualification.
- **Responsible role:** Operations + database operator. **Prerequisites:** H01/H02; recovery custody and release plan.
- **Security/privacy:** No public database port; separate app/migrator/recovery roles; provider snapshots also contain private data. **Cost implications:** Compute/storage/backup/PITR/IO and standby costs.
- **Acceptance test:** Exact-image upgrade twice, failure rollback, same-API recovery and sealed restore under actual host roles. **Blocks:** S2/S3 deployment; S6 hosted proof.

## H04 — Redis topology, network and per-class failure policy

- **Decision ID:** OD-HOSTED / H-REDIS-POLICY. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Redis topology, network and per-class failure policy. PROPOSED internal authenticated standalone Redis for first isolated rehearsal; managed private TLS if approved availability needs justify it; no HA claim.
- **Evidence available:** 37 unchanged buckets, 17 real Redis cases; two-instance campaign passes. **Missing evidence:** Owner topology choice, ACL/TLS/region/cost, outage policy approval and host failover drill.
- **Responsible role:** Operations + security + product owner. **Prerequisites:** H01/H02; explicit bucket decisions below.
- **Security/privacy:** No public 6379; namespace/HMAC secret shared; no raw candidate identifiers; no eviction of active counters. **Cost implications:** Memory/VM or managed-service/transfer/support costs.
- **Acceptance test:** Shared burst, forbidden ACL commands, unavailable/readiness/503/429/Retry-After and recovery on every API. **Blocks:** S2 deployment configuration; S6 host proof.

## H05 — Capacity and replica count

- **Decision ID:** OD-HOSTED. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Capacity and replica count. PROPOSED x86_64 Linux, starting planning envelope 8 vCPU/16 GiB and at least 100 GiB free after images, plus dataset/restore headroom; start 1 API/1 worker then controlled 2/2 drill.
- **Evidence available:** Task 07 two APIs/two workers qualified on one disposable host; no hosted load/peak-capacity result. **Missing evidence:** Owner workload/concurrency/storage limits and measured memory/CPU/IO including clamd, Next, PG and Chroma.
- **Responsible role:** Operations + engineering lead. **Prerequisites:** Approved hardware quote and limits; no same-host HA assumption.
- **Security/privacy:** Bound workload/storage; one VM remains one failure domain; do not claim cross-host volume or index safety. **Cost implications:** Compute, disk growth, load tests, standby/HA if later required.
- **Acceptance test:** Record load/error/queue/resource metrics at approved thresholds; prove volume identity and worker drain. **Blocks:** S1 sizing approval; S4/S6 measurement.

## H06 — Domains, DNS, frontend placement and TLS

- **Decision ID:** OD-HOSTED. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Domains, DNS, frontend placement and TLS. PROPOSED same-host Next.js/Caddy with approved sibling app/API domains under one parent; restrict access to named testers.
- **Evidence available:** Real nonce CSP, secure cookies, sign-in/logout, History images and SSE pass through Caddy. **Missing evidence:** Domains/DNS authority, certificate lifecycle, private access, real DNS/TLS and firewall proof.
- **Responsible role:** Operations + security. **Prerequisites:** H01/H02 and approved network/secret design.
- **Security/privacy:** Preserve nonce CSP, exact-origin CORS, trusted proxy boundary and cookie flags; ACME/DNS changes need explicit scope. **Cost implications:** Domain/DNS/IP/bandwidth/certificate operations costs.
- **Acceptance test:** Real certificate, hydration/negative injection, image, cookie/logout, CORS and spoof tests through approved edge. **Blocks:** S2/S4 deployment; S6 hosted proof.

## H07 — Persistent document/knowledge/index storage

- **Decision ID:** OD-HOSTED / PG-05. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Persistent document/knowledge/index storage. PROPOSED private encrypted POSIX volumes shared by API/worker on the same host; keep original development assets entirely separate.
- **Evidence available:** UID/private roots, foreign-user refusal, clean/EICAR and recovery bytes verified offline. **Missing evidence:** Host volume ownership/encryption/capacity, consistent snapshot and populated approved semantic-index restore evidence.
- **Responsible role:** Operations + knowledge lead. **Prerequisites:** H03/H05 and source/licence approvals for nonempty knowledge.
- **Security/privacy:** Never web-public/object-public; opaque paths, least privilege; shared filesystem or multi-host design needs new qualification. **Cost implications:** SSD/block capacity, snapshots and restore scratch storage.
- **Acceptance test:** Restart/redeploy checksums, owner-isolation and separate-target restore with real permissions. **Blocks:** S2 deployment; S6 source/index qualification.

## H08 — ClamAV signature supply, freshness policy and outage operator

- **Decision ID:** OD-MALWARE / OD-SCANNER-ALERT. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** ClamAV signature supply, freshness policy and outage operator. PROPOSED real clamd, approved mirror egress, persisted signatures, explicit freshness acceptance and safe outage alert.
- **Evidence available:** Real clamd 1.4.6/EICAR-only offline fixtures pass; uploads refuse outage. **Missing evidence:** Current supported image/digest, signed definitions/update cadence, freshness threshold and real host update/recovery evidence.
- **Responsible role:** Operations + security. **Prerequisites:** H01/H02 and egress/on-call approval.
- **Security/privacy:** Do not call EICAR-only definitions malware coverage; scanner unreachable must still refuse uploads. **Cost implications:** RAM/CPU, definition storage/downloads and alert operation.
- **Acceptance test:** Clean/EICAR, unreachable/stale definitions and restart/update tests; verify whether stale state blocks serving or only approval. **Blocks:** S2/S4 deployment prerequisites; S6 qualification.

## H09 — Release transport, image trust and registry choice

- **Decision ID:** OD-HOSTED / PG-12. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Release transport, image trust and registry choice. PROPOSED use existing checksummed offline export/load and local immutable IDs for first rehearsal; future registry optional and separately authorized.
- **Evidence available:** Build-once API/worker/migrate, matching web, manifests and local transfer verified. **Missing evidence:** Review main-SHA bundle for REAL approved domains, trusted anchors, transport access and any registry/signing design.
- **Responsible role:** Release owner + security. **Prerequisites:** Reviewed release SHA, x86 platform and owner-approved API origin.
- **Security/privacy:** Do not retag/promote a7/b463 reserved-example-domain web as real-domain build; local image ID is not a registry distribution digest. **Cost implications:** Build/transfer/archive storage; optional registry scanning/retention/egress.
- **Acceptance test:** Verify loaded content/source/anchors; wrong SHA/digest refusal; same backend identity; no image publication in this task. **Blocks:** S3 before first deployment.

## H10 — Runtime secrets and credential access

- **Decision ID:** OD-HOSTED / K-PROVIDER. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Runtime secrets and credential access. PROPOSED approved regional secret manager with read-only delivery to container UIDs; no repository dotenv copy; least-privilege operator delivery.
- **Evidence available:** Runtime secrets excluded from release context/manifests; safe errors verified. **Missing evidence:** Named store/account, access/revocation/rotation, host permissions and audit evidence.
- **Responsible role:** Security + operations. **Prerequisites:** H01/H02 and named custodians.
- **Security/privacy:** Separate SESSION/RATE_LIMIT/DB/master/provider credentials; file-based Compose secrets do not fix UID permissions automatically. **Cost implications:** Store, access requests, audit retention and rotation operations.
- **Acceptance test:** Canary secret never enters layers/logs/manifests; actual UID 10001/Redis 999 access and deny tests. **Blocks:** S2 deployment.

## R01 — Backup destination, residency and independently controlled storage

- **Decision ID:** PG-09 / OD-HOSTED. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Backup destination, residency and independently controlled storage. PROPOSED sealed sets on separately controlled off-host EU storage; independent restore destination and trusted latest erasure head.
- **Evidence available:** Encrypted local transfer/restore verified; no cloud adapter or off-host upload qualification. **Missing evidence:** Provider/bucket/account/region, IAM, version/snapshot inventory, transfer procedure and external receipt.
- **Responsible role:** Operations + privacy qualifier. **Prerequisites:** H01/H02, keys and retention decision.
- **Security/privacy:** Provider snapshots/replicas/versions are additional copies; object storage is not a drop-in POSIX document/index root. **Cost implications:** Stored GB, versions, requests, egress, restore scratch and custody overhead.
- **Acceptance test:** Authorized off-host copy/verify/new-target restore with independently retrieved current ledger head. **Blocks:** S2 backup design; S6 actual drill.

## R02 — Encryption, signing, ledger/master-key custody and escrow

- **Decision ID:** PG-09 / OD-HOSTED. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Encryption, signing, ledger/master-key custody and escrow. PROPOSED named separate custody/access policies and dual review; no key material in this packet.
- **Evidence available:** Sealed sets use BACKUP_ENCRYPTION_KEY and derived manifest authentication; independent ledger key/head and SECRET_STORE_MASTER_KEY are external. **Missing evidence:** Custodian/escrow/recovery access, rotation, key-loss procedure and any required separate signing-key design.
- **Responsible role:** Security lead + key custodian + privacy qualifier. **Prerequisites:** H10; approved source/destination/ledger access separation.
- **Security/privacy:** Sealed manifest authentication derives from sealing key; optional BACKUP_SIGNING_KEY is not proof of independent sealed-set signing custody. Do not claim cryptographic key separation absent review. **Cost implications:** Secret/escrow/rotation/access audit and drill costs.
- **Acceptance test:** Authorized wrong-key/tamper/escrow restore and rotation plan; no key generation in Task 08. **Blocks:** S2 before sensitive hosted storage.

## R03 — Retention, erasure windows and provider-copy disposal

- **Decision ID:** PG-04 / PG-09. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Retention, erasure windows and provider-copy disposal. PROPOSED retain 35-day engineering defaults only as proposals pending counsel; inventory every copy and resolve immutable retention versus erasure duties.
- **Evidence available:** Erasure ledger/reapplication, rewrite and destruction-attestation tooling; no legal approval. **Missing evidence:** Owner/counsel retention and deletion schedule across app, backups, snapshots, versions, logs, keys and contracts.
- **Responsible role:** Privacy/legal qualifier + operations. **Prerequisites:** R01/R02; jurisdiction/data classification.
- **Security/privacy:** Live deletion does not instantly erase backup copies; no complete-erasure claim without verified disposition. **Cost implications:** Retention/versions, rewrite scratch, audit and legal review.
- **Acceptance test:** Approved schedule plus rehearsal of due erasure/rewrite/disposal and independent attestations. **Blocks:** S2 before data-bearing deployment; S7 legal acceptance.

## R04 — RPO/RTO and disaster-recovery rehearsal criteria

- **Decision ID:** PG-09 / OD-GATE-THRESHOLDS. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** RPO/RTO and disaster-recovery rehearsal criteria. OPEN: owner sets numerical objectives from data-loss tolerance; no target inferred from tiny fixture timings.
- **Evidence available:** Offline restore durations and failure controls recorded only at synthetic size. **Missing evidence:** Data scale, backup cadence, provider failure scenarios, timed reconciliation and approval targets.
- **Responsible role:** Product owner + incident commander + operations. **Prerequisites:** R01-R03 and named recovery owners.
- **Security/privacy:** Recovery time includes isolation, transfer, erasure/accounting reconciliation and authorization; not just pg_restore. **Cost implications:** Backup frequency, standby/scratch/storage/transfer and on-call costs.
- **Acceptance test:** Timed host/region loss and new-target restore meeting approved objectives with preserved usage/deletions. **Blocks:** S1/S2 scope decision; S6 acceptance.

## R05 — Restore operators, incident commander, reconciliation and hold-release authority

- **Decision ID:** PG-09 / OD-RESOURCE. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Restore operators, incident commander, reconciliation and hold-release authority. PROPOSED named distinct operational reviewer and executing database operator; release hold only after legitimate written reconciliation.
- **Evidence available:** Persistent database/file hold, AI kill, API503/worker0 and conservative unknown reservations verified. **Missing evidence:** Named operators/commander/authority, current provider receipts, ledger ownership, audit destination and escalation.
- **Responsible role:** Product owner + operations + finance/reconciliation owner. **Prerequisites:** R01-R04, valid release and fresh erasure/budget records.
- **Security/privacy:** Fence all old/new producers; preserve unsettled runs/unknown costs; recycle connections after authorized hold change; no release here. **Cost implications:** Staffing/on-call and incident/drill effort.
- **Acceptance test:** Signed source/target/ledger/usage reconciliation and approved release; target stays held on any gap. **Blocks:** S2 operator readiness; S6 recovery release.

## R06 — Application rollback authority and compatibility

- **Decision ID:** PG-09 / PG-15. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Application rollback authority and compatibility. PROPOSED forward-fix first; only reviewed compatible image rollback with fresh drained state and zero active/unsettled work.
- **Evidence available:** Rollback rejects wrong schema/capability/held/unsettled state; rollback profile omits migrate. **Missing evidence:** Named approval, previous qualified bundle, host state/physical target identity and rollback rehearsal.
- **Responsible role:** Release owner + operations + incident commander. **Prerequisites:** H09/R05, schema0048/budget2/recovery1 compatibility.
- **Security/privacy:** Never downgrade automatically, overwrite source data or reset reservations to force rollback; restore is separate new-target authority. **Cost implications:** Previous artifacts, backup/scratch and incident effort.
- **Acceptance test:** Wrong-schema/unsettled rollback refusal; matching app/web rollback under approved drain; recovery separately reviewed. **Blocks:** S3 plan and S6 rehearsal; production approval separate.

## S01 — Network controls, egress and privileged access

- **Decision ID:** OD-HOSTED / PG-09. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Network controls, egress and privileged access. PROPOSED only approved Caddy ingress; private DB/Redis/clamd, MFA/admin access and deny paid-provider egress during S4.
- **Evidence available:** Private internal campaign, forged-proxy/CORS/ownership refusal pass. **Missing evidence:** Real firewall/routes/private admin access/DNS, allowed ACME/signature/store endpoints and egress tests.
- **Responsible role:** Security + operations. **Prerequisites:** H01/H02/H06/H10.
- **Security/privacy:** No public DB/Redis/scanner or candidate storage; all third-party/control-plane processing locations require review. **Cost implications:** IP, firewall/VPN, NAT/egress and access audit costs.
- **Acceptance test:** External/internal port scans and approved endpoint allow/deny probes, no secrets in logs. **Blocks:** S2/S4 deployment.

## S02 — Monitoring, alert routing and incident response

- **Decision ID:** OD-HOSTED / PG-09. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Monitoring, alert routing and incident response. PROPOSED use existing safe readiness/Admin/worker/budget observations; owner chooses external collector and bounded alerts.
- **Evidence available:** DB/data-root/shared-Redis readiness, worker heartbeat, scanner status and budget/hold signals exist. **Missing evidence:** Collector/log residence/retention, on-call names, severity/detection targets and delivery/recovery drills.
- **Responsible role:** Operations + incident commander + privacy qualifier. **Prerequisites:** S01/H10/R05 and approved telemetry fields.
- **Security/privacy:** Worker/scanner reports are not universally traffic gates; alert and upload refusals separately verify. No cookies, candidate text, prompts or raw provider events. **Cost implications:** Metrics/log ingestion/retention, paging, staff and drills.
- **Acceptance test:** Trigger real host dependency outage, verify alert/ack/escalation/recovery and absence of private data. **Blocks:** S2/S4 instrumentation; S6 acceptance.

## A01 — Written spending authorization and private configuration

- **Decision ID:** OD-BUDGET. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Written spending authorization and private configuration. OPEN: no ceilings, price/model allowlist or marker proposed; owner completes the exact worksheet below.
- **Evidence available:** Durable total/class/category/request/concurrency/kill/unknown accounting tested offline. **Missing evidence:** Every owner input, signed evidence reference, protected config/marker delivery and explicit evaluation purposes.
- **Responsible role:** Budget owner + approver + reconciliation/incident owners. **Prerequisites:** Named owners, privacy review, approved datasets and model pricing.
- **Security/privacy:** Keep enforce/closed with missing approval; USD-only runtime; no reuse of historic demo credit or reset of unknown costs. **Cost implications:** AI spend separately approved from infrastructure; pricing and exchange assumptions frozen by owner.
- **Acceptance test:** Missing/mismatched/expired/model/price/cap/concurrency/unknown refusal with zero transport before separately authorized live call. **Blocks:** S5 paid calls, not S4 zero-paid-call rehearsal.

## A02 — Provider data handling, embedding choice, source licences and markets

- **Decision ID:** K-PROVIDER / OD-EMBED / OD-US-CONTENT / OD-LANG-02. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Provider data handling, embedding choice, source licences and markets. PROPOSED preserve OpenRouter primary-provider direction; select exact models/markets only after approved benchmark and licensing/privacy review.
- **Evidence available:** Hash embedding refused in hosted mode; manifest/source/market guards, empty approval register and 07B preflight exist. **Missing evidence:** Subprovider retention/region/training terms, source licences, exact model/dimensions/version/pricing and per-market authority.
- **Responsible role:** Privacy/legal + licensing + knowledge lead + owner. **Prerequisites:** A01 and independent reviewers/thresholds.
- **Security/privacy:** EU VM alone cannot constrain model processing; unapproved sources and cross-market factual claims remain refused. **Cost implications:** Licences, embeddings/index build/storage, approved evaluations and legal review.
- **Acceptance test:** Frozen licensed corpus, retrieval/citation/market tests and data-processing approval; mismatch refuses. **Blocks:** S5/S6 source/live qualification; empty-source refusal rehearsal allowed S4.

## L01 — Synthetic development-class path versus qualified hosted locale and release/expiry binding

- **Decision ID:** OD-STAGING-LANGUAGES / OD-APPROVED-UNTIL. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Synthetic development-class path versus qualified hosted locale and release/expiry binding. PROPOSED strict staging stays closed; owner chooses qualification protocol, initial test locale and expiry/SHA rules without reducing seven-language S1.
- **Evidence available:** All seven offered=false; 06H validates all14 gates, per-language evidence and hosted refusal. **Missing evidence:** Written path/data/network boundaries and valid human/legal/gate evidence; resolve qualification bootstrap before positive hosted traffic.
- **Responsible role:** Product owner + native/legal/security qualifiers. **Prerequisites:** Governance, A01/A02 as applicable; secure harness for any development-class exercise.
- **Security/privacy:** No API_ENV override presented as hosted qualification; development identity fallback is unsafe on an exposed host. **Cost implications:** Isolated exercise, seven reviewers/legal translation and scheduling cost.
- **Acceptance test:** Negative registration/activity tests remain; no real-user activation until legitimate complete release-bound records. **Blocks:** S4 refusal tests allowed; S5-S7 positive journeys blocked.

## Q01 — Grounding/agent-policy protocol, datasets, thresholds and independent review

- **Decision ID:** 07B / OD-HELDOUT-AUTHOR / OD-GATE-THRESHOLDS / OD-COVERAGE. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Grounding/agent-policy protocol, datasets, thresholds and independent review. PROPOSED frozen version/hash, per-language/market slices and report-only until owner thresholds and spending approved.
- **Evidence available:** 07B RAGAS audit/preflight; historical zero-score cause unresolved; deterministic guards and tool parity pass. **Missing evidence:** Independent author/reviewers, licences, benchmark/rubric/sample size, thresholds, run/version/pricing identity and budget.
- **Responsible role:** AI safety/quality lead + independent evaluators + owner. **Prerequisites:** A01/A02/L01 and observability; investigate zero-score cause before larger run.
- **Security/privacy:** Synthetic/public approved inputs only; no candidate private corpus, hidden prompt disclosure or contamination masked as held-out. **Cost implications:** Bounded evaluator/model/embedding requests and independent reviewer effort.
- **Acceptance test:** Per-language grounding/citation/retrieval/tool safety against approved thresholds; any mandatory failure blocks qualification and gets focused remediation. **Blocks:** S5/S6 live qualification, not initial infrastructure refusal tests.

## Q02 — Hosted OCR/document quality protocol

- **Decision ID:** 07C / J-OCR / OD-BUDGET. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Hosted OCR/document quality protocol. PROPOSED approved synthetic/licensed image/PDF set per seven locales, frozen engine/config/version/hash and independent transcription rubric.
- **Evidence available:** 14 local synthetic OCR observations and real offline clamd/document pipeline; no hosted quality sign-off. **Missing evidence:** Approved documents, reference transcriptions, numeric quality thresholds, scanner freshness/privacy/retention and reviewer identities.
- **Responsible role:** Document/quality lead + native reviewers + security. **Prerequisites:** H07/H08/S02, L01; A01 only for a paid path.
- **Security/privacy:** No real CVs or private uploads; preserve ownership/scanning. OCR may be local but any paid OCR/embedding/model path still requires explicit authority. **Cost implications:** OCR compute/storage/native review; paid service costs only if explicitly selected.
- **Acceptance test:** Hosted ingest/OCR/isolation/scanner/outage plus per-language error metrics under approved rubric; failures preserved. **Blocks:** S6 residual qualification; basic offline refusal tests already verified.

## G01 — Name all governance, operational and independent reviewers

- **Decision ID:** 00A / OD-RESOURCE / OD-LANG-03 / OD-LANG-04. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Name all governance, operational and independent reviewers. OPEN: appoint people, backups, dates, conflicts and evidence owners; automation cannot substitute.
- **Evidence available:** Engineering review packs, protocols, blank forms and role-based controls exist. **Missing evidence:** Named operations/security/AI/native/legal/licensing/incident/product/release owners; signed independent reviews.
- **Responsible role:** Product owner. **Prerequisites:** Availability and conflicts declared; full S1 retained.
- **Security/privacy:** No invented appointments/signatures; Admin remains not a private-candidate-data superuser. **Cost implications:** Staffing, native/legal/security review and on-call budget.
- **Acceptance test:** Appointment record with role/access/independence, start/due dates and signed scoped deliverables. **Blocks:** S1 operations appointment; S7/S8 remaining human/release gates.

## G02 — Disposition of ten reclassification proposals and full S1 scope

- **Decision ID:** 00B / OD-RECLASS / OD-SCOPE-01. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Disposition of ten reclassification proposals and full S1 scope. PROPOSED keep all S1 obligations pending explicit item-level owner disposition; no deadline-driven scope cut.
- **Evidence available:** S1 approved; 452 issues reconciled with zero unmapped and historical failed gates retained. **Missing evidence:** Explicit item-level decisions if any change requested; owner confirmation of all unresolved product policies.
- **Responsible role:** Product/release owner. **Prerequisites:** Owner reviews register and full package list.
- **Security/privacy:** No removal of mandatory security/privacy/source/language obligations by engineering or staging approval. **Cost implications:** Full-scope staffing and schedule; date moves rather than silent scope loss.
- **Acceptance test:** Reconciliation remains 452/0; every disposition has its owner provenance and unchanged historical results. **Blocks:** S7/S8 scope acceptance; does not authorize deployment.

## I01 — Real email/OIDC activation and invitation operators

- **Decision ID:** OD-INVITE-EMAIL / OD-INVITE-ISSUERS / PG-02. **Authorization:** OPEN / NOT AUTHORIZED.
- **Required / proposed:** Real email/OIDC activation and invitation operators. PROPOSED leave external email/OIDC off during S4; independently authorize provider/domains/issuers/test recipients later.
- **Evidence available:** Invitation-only policy, secure opaque sessions, memory-email real auth flows pass. **Missing evidence:** Provider/privacy/spend approval, sender DNS, controlled recipients, live recovery/verification and IdP values supplied by owner.
- **Responsible role:** Security + operations + product owner. **Prerequisites:** S5 explicit service activation and H10/A02 privacy approval.
- **Security/privacy:** Never invent IdP IDs or send to real candidates; no new delegated permission by default. **Cost implications:** Email/identity vendor, DNS and verification operations costs.
- **Acceptance test:** Authorized recipient round trip, webhook authenticity/idempotency, invitation/expiry/revocation and OIDC-or-disabled evidence. **Blocks:** S5 live identity; not S4 zero-paid-call/refusal work.

## OD-BUDGET — exact written inputs before any paid request

Status **OPEN**. The existing [Task 05 specification](OD_BUDGET_SPECIFICATION_TASK05.md) and `src/llm/budget/config.py` are authoritative. This packet creates no runtime JSON, marker, provider credential or approval. Infrastructure estimates in the main packet are unrelated to AI spending authority.

| Owner input | Exact binding / requirement |
|---|---|
| Owner, approver, environment and evidence | Named owner/approver, exact API_ENV, dated written authorization/reference and authorized operator; runtime marker matches only legitimately approved private configuration. |
| Currency and aggregate ceiling | Runtime accepts USD only; integer micro-USD rounds up. Owner supplies total hard_cap_usd, lower stop_usd and max_requests. If authorizing in EUR, obtain an explicit approved USD conversion/ceiling before use; no implicit conversion or code currency extension. |
| Evaluation period and expiry | UTC/timezone-aware period_start and expires_at; evaluation purpose, permitted datasets and period spending allocation; no inherited EUR10/USD historical credit. |
| Class/category allocations | development/evaluation/production classes actually needed, each hard/stop/request cap; agent/interview/embedding/evaluation category hard/stop allocations, each within class and aggregate. Hosted cannot use development class. No class/category is automatically funded. |
| Provider/model/version/prices | Explicit allowed_provider_hosts; exact model IDs/version or pinned provider routing, dimensions for embeddings; pricing.models prompt/completion USD per token, cited pricing_source, pricing_effective_at and pricing_expires_at within approval lifetime. No free/unlimited model assumption. |
| Tokens, timeouts, retries and concurrency | limits.max_input_tokens, max_output_tokens, request_timeout_s, max_retries, max_concurrency and dedupe_window_s. Existing runtime clamps connect/read/write/pool timeouts to the one approved request_timeout_s (and any shorter existing adapter timeout); distinct phase limits would require a separate reviewed change. |
| Stop and reconciliation | Lower stop thresholds, total/category hard stop, durable kill/overrun response, ambiguous-outcome handling, reconciliation_owner and incident_owner/escalation; preserve unknown reservations/usage until independently reconciled. |
| Secret/configuration custody | Owner delivers protected private file and matching AI_BUDGET_APPROVED_MARKER via approved secret delivery. Record only evidence reference here, never actual values. Changed policy hash/new period requires drained authorized reconciliation, not ledger reset. |
| Authorized purposes and failure procedure | Written permitted evaluation tasks/data/recipients and request bounds; no implicit general provider activation. Stop on threshold failure, expiry, pricing drift, unknown charge or data incident, fence producers, retain evidence and get renewed authority. |

Until approved, enforce mode with CLOSED governor is the intended refusal state; absent/mismatched/expired configuration, model/price/cap errors and CI all refuse paid transport. A secret marker is a runtime check, not a substitute for written owner authorization. No paid test is run here.

## H-REDIS-POLICY — all 37 current buckets, proposals only

Current numeric limits and **local** outage defaults verified from `src/api/rate_limit.py` and the [37-bucket audit](WAVE4_TASK04_REDIS_AUDIT.md). No source policy is edited. The two observe-only Practice/Career buckets remain observe-only until separately authorized; deferred speech/realtime/billing stay disabled.

| Bucket | Requests/window seconds | Scope | Current | PROPOSED hosted outage behavior |
|---|---:|---|---|---|
| `auth_login_ip` | 20/300 | ip | local | deny, subject to owner approval |
| `auth_login_account` | 8/300 | account | local | deny, subject to owner approval |
| `auth_register_ip` | 8/3600 | ip | local | deny, subject to owner approval |
| `auth_verify_resend` | 5/3600 | account | local | deny, subject to owner approval |
| `auth_verify_resend_cooldown` | 1/60 | account | local | deny, subject to owner approval |
| `auth_forgot_ip` | 6/3600 | ip | local | deny, subject to owner approval |
| `auth_forgot_account` | 4/3600 | account | local | deny, subject to owner approval |
| `auth_reset_ip` | 12/3600 | ip | local | deny, subject to owner approval |
| `auth_oidc_start_ip` | 30/3600 | ip | local | deny, subject to owner approval |
| `auth_global` | 2000/300 | global | local | deny, subject to owner approval |
| `auth_invitation_ip` | 10/3600 | ip | local | deny, subject to owner approval |
| `auth_invitation_global` | 400/3600 | global | local | deny, subject to owner approval |
| `cost_agent_user` | 60/3600 | user | local | deny, subject to owner approval |
| `cost_interview_user` | 120/3600 | user | local | deny, subject to owner approval; enforcement still observe-only |
| `cost_career_user` | 60/3600 | user | local | deny, subject to owner approval; enforcement still observe-only |
| `cost_research_user` | 30/3600 | user | local | deny, subject to owner approval |
| `cost_upload_user` | 40/3600 | user | local | deny, subject to owner approval |
| `cost_realtime_user` | 12/3600 | user | local | deny, subject to owner approval |
| `cost_speech_stt_user` | 60/3600 | user | local | deny, subject to owner approval |
| `cost_speech_tts_user` | 120/3600 | user | local | deny, subject to owner approval |
| `cost_global` | 5000/3600 | global | local | deny, subject to owner approval |
| `support_create_user` | 10/3600 | user | local | deny, subject to owner approval |
| `support_reply_user` | 60/3600 | user | local | deny, subject to owner approval |
| `privacy_request_user` | 5/3600 | user | local | local, bounded per process; owner/legal review required |
| `legal_accept_user` | 30/3600 | user | local | local, bounded per process; owner/legal review required |
| `stepup_user` | 5/300 | user | local | deny, subject to owner approval |
| `invitation_issue_user` | 60/3600 | user | local | deny, subject to owner approval |
| `admin_bulk_user_actions` | 10/3600 | user | local | deny, subject to owner approval |
| `role_request_user` | 20/3600 | user | local | deny, subject to owner approval |
| `role_approve_user` | 30/3600 | user | local | deny, subject to owner approval |
| `email_test_user` | 3/3600 | user | local | deny, subject to owner approval |
| `billing_checkout_user` | 10/3600 | user | local | deny, subject to owner approval |
| `billing_status_ip` | 120/300 | ip | local | deny, subject to owner approval |
| `billing_webhook_ip` | 600/60 | ip | local | deny, subject to owner approval |
| `mail_webhook_ip` | 600/60 | ip | local | deny, subject to owner approval |
| `billing_recovery_user` | 20/3600 | user | local | deny, subject to owner approval |
| `billing_summary_user` | 120/300 | user | local | deny, subject to owner approval |

| Policy class | Distributed/availability consequence | Alert/recovery acceptance |
|---|---|---|
| Auth, privileged/security, provider-cost, support abuse and signed webhooks — PROPOSED deny | Preserve refusal on missing shared protection; lose affected availability; 503/Retry-After differs from 429 ceiling. Webhook redelivery must retain idempotent accounting. Disabled routes are not activated. | Alert on lost shared protection/deny events, verify each replica and operator response, recover without automatic write replay. |
| Privacy request/legal acceptance — PROPOSED local exception | Availability favored for these existing non-AI writes, but N replicas may admit N local ceilings; local histories never merge into Redis, recovery can admit further requests. No global guarantee. Owner/counsel may instead require deny after reviewing access consequences. | Alert on fallback deltas, abuse and recovery; approve availability limits/alternative support procedure explicitly. |
| All classes | RATE_LIMIT_SHARED_REQUIRED readiness can remove a degraded replica from rotation, so local fallback does not guarantee public availability if all replicas are unready. Redis cannot replace PG durable admission or monetary enforcement. | Proposed alert on any degraded/fail-closed state; owner sets page/SLO thresholds. Verify bounded pool waits, ACL/namespace/secret alignment, restart counter reset and maximum3600s-window drain/rotation policy. |

The separate in-memory realtime session/concurrency guard retains its local scope and disabled-feature boundary. Managed Cluster/Sentinel/HA behavior is not qualified by standalone Redis tests. No global failure rule is approved.

## Full unresolved register crosswalk

The following inventory carries every row of the register's current open-decision tables and its dated historical pending table, including future/unscheduled commercial and academic items. It does **not** turn every historical row into a staging prerequisite. Owner-approved S1 and resolved language/release-train directions remain requirements. Engineering delivery may supersede an old technical observation (for example stale database counts) without supplying an owner disposition. Review unresolved aliases with the owner; do not silently close, reclassify or reduce scope. Refer to [the full register](../OWNER_DECISION_REGISTER.md) for detail, release and provenance. H-REDIS-POLICY and the operational worksheet cards above are additional explicit staging dependencies.

| ID | Recorded decision | Provenance / current handling |
|---|---|---|
| OD-RESOURCE | Allocate the additional time and engineering resources the owner is prepared to provide | Current open table; OPEN AS RECORDED |
| OD-LANG-02 | Approve each proposed primary market individually | Current open table; OPEN AS RECORDED |
| OD-LANG-03 | Name the native-language reviewer for each of the seven languages | Current open table; OPEN AS RECORDED |
| OD-LANG-04 | Name the legal and privacy translation qualifier(s) | Current open table; OPEN AS RECORDED |
| OD-RU-FUTURE | Whether and when Russian is ever activated | Current open table; OPEN AS RECORDED |
| OD-HOSTED | Authorise and choose the hosted environment | Current open table; OPEN AS RECORDED |
| OD-BUDGET | Approve a bounded live-evaluation and live-provider budget for qualification | Current open table; OPEN AS RECORDED |
| OD-GATE-THRESHOLDS | Approve numeric thresholds for the quality and safety gates | Current open table; OPEN AS RECORDED |
| OD-BULK-ACTIONS | Which restricted bulk user actions are permitted | Current open table; OPEN AS RECORDED |
| OD-REPORT-EXPORT | Which export formats the reports support | Current open table; OPEN AS RECORDED |
| OD-WS-TRANSFER | Workspace ownership transfer rules | Current open table; OPEN AS RECORDED |
| OD-COVERAGE | Approve the separate frozen R1.0 beta-scope coverage measure | Current open table; OPEN AS RECORDED |
| OD-ACADEMIC-01 | Confirm retirement of the academic-only capstone-submission tasks | Current open table; OPEN AS RECORDED |
| OD-EMBED | Choose the production embedding provider and model | Current open table; OPEN AS RECORDED |
| OD-DEFER-PLACEMENT | Confirm placement of items that fit no agreed release theme | Current open table; OPEN AS RECORDED |
| OD-PLAN-LIMITS | Which limits and allowances Basic and Premium carry during the free beta | Current open table; OPEN AS RECORDED |
| OD-US-CONTENT | May US-sourced content appear at all, as clearly labelled non-EU general information? | Current open table; OPEN AS RECORDED |
| OD-RECLASS | Item-level disposition of the ten proposed reclassifications | Current open table; OPEN AS RECORDED |
| OD-INVITE-EMAIL | Send invitation emails? | Current open table; OPEN AS RECORDED |
| OD-INVITE-ISSUERS | Who may issue and revoke invitations | Current open table; OPEN AS RECORDED |
| OD-PLAN-ACTIVATION-APPROVAL | Second approver for plan activation and bulk assignment | Current open table; OPEN AS RECORDED |
| OD-STAGING-LANGUAGES | How to test a hosted stack while no language is qualified | Current open table; OPEN AS RECORDED |
| OD-APPROVED-UNTIL | Is `approved_until` mandatory, and must the release SHA descend from the deployed build | Current open table; OPEN AS RECORDED |
| OD-SCANNER-ALERT | Own alert category for a scanner outage | Current open table; OPEN AS RECORDED |
| OD-FAKE-SCANNER-GUARD | Make fake-scanner records a blocking serving-guard finding in hosted environments | Current open table; OPEN AS RECORDED |
| OD-WS-ADMIN-ENROL | Platform Admin enrolling an ordinary account into a Workspace | Current open table; OPEN AS RECORDED |
| OD-STORY-PREPARE-CONSENT | Per-story picker and per-run consent in Prepare | Current open table; OPEN AS RECORDED |
| OD-HELDOUT-AUTHOR | Who authors the independent injection held-out set | Current open table; OPEN AS RECORDED |
| OD-INPUT-GUARD-LANGUAGES | Multilingual rules for the interview input guard | Current open table; OPEN AS RECORDED |
| OD-LEGACY-ROUTES | Retire the legacy Admin user status, plan and revoke routes | Current open table; OPEN AS RECORDED |
| OD-LOCAL-TEST-ENV | Rebuild the local fresh-dependency venv and Playwright browser cache | Current open table; OPEN AS RECORDED |
| OD-STALE-02A-TEST | Retire or rebase the branch-relative 02A forbidden-files test | Current open table; OPEN AS RECORDED |
| IR-DEADLINE | Course deadline and time zone are unconfirmed (planning documents say 2026-10-20 | Historical pending; OPEN AS RECORDED |
| IR-DEPLOY-EXPECT | Does local execution satisfy the course deployment expectation? | Historical pending; OPEN AS RECORDED |
| IR-RC004-SPEC | No dedicated RC-P10-004 entry-criteria specification existed | Historical pending; OPEN AS RECORDED |
| B-EMBED-SEL | Embedding provider and model selection | Historical pending; OPEN AS RECORDED |
| C-PROTO | Reviewer protocols and rating rubric for AI quality | Historical pending; OPEN AS RECORDED |
| C-THRESH | Owner thresholds for AI quality | Historical pending; OPEN AS RECORDED |
| D-21 | D-21 name who performs qualified legal review | Historical pending; OPEN AS RECORDED |
| F2B1-OD-01 | Legal seller entity | Historical pending; OPEN AS RECORDED |
| F2B1-OD-02 | Product classification (automated digital product) | Historical pending; OPEN AS RECORDED |
| F2B1-OD-03 | Product tax code | Historical pending; OPEN AS RECORDED |
| F2B1-OD-04 | What Premium includes beyond Basic | Historical pending; OPEN AS RECORDED |
| F2B1-OD-05 | Premium monthly price | Historical pending; OPEN AS RECORDED |
| I-ALLOW | Numerical Basic/Premium allowances not approved | Historical pending; OPEN AS RECORDED |
| I-ENT-POLICY | Paid entitlement policy unapproved | Historical pending; OPEN AS RECORDED |
| I-FAST | Basic-to-Fast transition not approved | Historical pending; OPEN AS RECORDED |
| I-PREMIUM-PRICE | Premium pricing and Basic/Premium product matrix commercial approval | Historical pending; OPEN AS RECORDED |
| IR-DEVDB-STALE | The developer database is 12 Alembic revisions behind the code head | Historical pending; OPEN AS RECORDED |
| IR-RAGAS-LIVE-APPROVAL | Live RAGAS evaluation awaits the owner's spending approval and three prerequisit | Historical pending; OPEN AS RECORDED |
| K-PROVIDER | Third-party model provider data handling for real candidate data | Historical pending; OPEN AS RECORDED |
| SJA-05 | Knowledge approval has no distinct-actor rule or step-up | Historical pending; OPEN AS RECORDED |
| B-COVEVAL | Decision whether to change coverage evaluator to check data origin/country (F-CO | Historical pending; OPEN AS RECORDED |
| C-USD15 | USD 15 extra ceiling not approved; 15 calls remain | Historical pending; OPEN AS RECORDED |
| D-01 | D-01 adopt or amend recovered GKB/C1-C4 specification | Historical pending; OPEN AS RECORDED |
| D-02 | D-02 adopt ambiguity-state and recency/eligibility policy | Historical pending; OPEN AS RECORDED |
| F2B-D22 | D-22 ASHE weekly never annualised; unanswered | Historical pending; OPEN AS RECORDED |
| F2B1-OD-06 | Premium annual price (no annual plan exists) | Historical pending; OPEN AS RECORDED |
| F2B1-OD-07 | Currency | Historical pending; OPEN AS RECORDED |
| F2B1-OD-08 | Tax-inclusive presentation | Historical pending; OPEN AS RECORDED |
| F2B1-OD-09 | Supported customer countries | Historical pending; OPEN AS RECORDED |
| F2B1-OD-10 | B2B subscriptions | Historical pending; OPEN AS RECORDED |
| F2B1-OD-11 | Trial policy | Historical pending; OPEN AS RECORDED |
| F2B1-OD-12 | Failed-payment grace period | Historical pending; OPEN AS RECORDED |
| F2B1-OD-13 | Cancellation policy | Historical pending; OPEN AS RECORDED |
| F2B1-OD-14 | Refund policy | Historical pending; OPEN AS RECORDED |
| F2B1-OD-15 | Dispute entitlement policy | Historical pending; OPEN AS RECORDED |
| F2B1-OD-16 | Billing data retention | Historical pending; OPEN AS RECORDED |
| H-REDIS-POLICY | Redis failure policy per bucket undecided | Historical pending; OPEN AS RECORDED |
| I-GRANDFATHER | Grandfathering of existing candidates | Historical pending; OPEN AS RECORDED |
| I-HISTORY-SHARE | Existing-share policy before history activation | Historical pending; OPEN AS RECORDED |
| I-RESET | Quota reset periods not approved | Historical pending; OPEN AS RECORDED |
| K-ATTR | Attribution wording decisions | Historical pending; OPEN AS RECORDED |
| K-LEGALACC | Legal acceptance of owner policy decisions | Historical pending; OPEN AS RECORDED |
| M-LEDGER | Mo and company-research cost-ledger gap | Historical pending; OPEN AS RECORDED |
| PRIV-BILL-RET | Billing data retention and erasure review | Historical pending; OPEN AS RECORDED |
| PRIV-POLICY01 | Verified-email policy (POLICY-01) | Historical pending; OPEN AS RECORDED |
| PRIV-RET | No retention periods for candidate content | Historical pending; OPEN AS RECORDED |
| W9.8-D7 | Original-file export bundle | Historical pending; OPEN AS RECORDED |
| A-AGG | Five BLS-specific aggregates quarantined | Historical pending; OPEN AS RECORDED |
| D-05 | D-05 padded ISCO identity and plan for 21 legacy rows | Historical pending; OPEN AS RECORDED |
| D-06 | D-06 baseline manifest freeze (GKB-0) | Historical pending; OPEN AS RECORDED |
| D-07 | D-07 ESCO language releases | Historical pending; OPEN AS RECORDED |
| D-10 | D-10 FX and PPP sources and methodology | Historical pending; OPEN AS RECORDED |
| D-11 | D-11 secondary-data qualification criteria | Historical pending; OPEN AS RECORDED |
| D-14 | D-14 regional-geography classification rule (policy p10c-d/1) | Historical pending; OPEN AS RECORDED |
| D-16 | D-16 precedence category for non-Eurostat harmonised sources (ILOSTAT) | Historical pending; OPEN AS RECORDED |
| D-17 | D-17 evidence-state vocabulary adoption | Historical pending; OPEN AS RECORDED |
| D-18-19 | D-18 / D-19 South America region vocabularies and national classifications | Historical pending; OPEN AS RECORDED |
| IR-REHEARSAL-CALL | One unplanned live agent run during the P11 rehearsal (outside the P10E ledger) | Historical pending; OPEN AS RECORDED |
| J-OIDC-PWD | OIDC-only users cannot set a password via recovery | Historical pending; OPEN AS RECORDED |
| M-LEGACY01 | Legacy Streamlit UI retained (LEGACY-01) | Historical pending; OPEN AS RECORDED |
| M-POLICY02 | Evaluation score consistency (POLICY-02) | Historical pending; OPEN AS RECORDED |
| PRIV-SUPPORT-NOTICE | Support data / privacy request response time | Historical pending; OPEN AS RECORDED |
| SJA-01 | AI config: second approver must be a second Platform Admin | Historical pending; OPEN AS RECORDED |
| SJA-02 | Knowledge Admin cannot retry/cancel failed jobs | Historical pending; OPEN AS RECORDED |
| SJA-03 | Billing/Security-Privacy admins cannot see queue state | Historical pending; OPEN AS RECORDED |
| SJA-04 | Operations Admin partly useful Review/Diagnostics | Historical pending; OPEN AS RECORDED |
| W9.8-D1b | Preparation-chat selective deletion | Historical pending; OPEN AS RECORDED |
| W9.8-D3 | Bulk memory deletion | Historical pending; OPEN AS RECORDED |
| W9.8-D4 | Per-version document deletion | Historical pending; OPEN AS RECORDED |
| W9.8-D5 | Auth-session list/revoke UI | Historical pending; OPEN AS RECORDED |
| W9.8-D6 | Feedback list and deletion page | Historical pending; OPEN AS RECORDED |
| W9.8-D8 | Orphan workspace invitations to a deleted user's email | Historical pending; OPEN AS RECORDED |
