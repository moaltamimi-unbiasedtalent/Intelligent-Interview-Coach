# P10C-F2A — Human Review and Approval Package

**Status: HUMAN APPROVAL PENDING.** The package below is complete and ready for named human reviewers. **Nothing is `qualified`:** 0 of 16,140 measurement records, 0 of 5 aliases and 0 sources. No reviewer identity was invented, no appointment was made, no persistent registry state changed, and no human decision was made on anyone's behalf. Compensation V2 and all 12 gates remain disabled. Machine-readable packet: `p10c_f2a/human_review_packet.json`; per-record review sheet (blank decision columns): kept in the isolated staging area, reproduced by `scripts/p10c_f2ar_packet.py`.

## 1. Owner decisions recorded (2026-10-18; basis: your explicit instruction, no signature or legal approval claimed)
D-08 alias review methodology APPROVED (no individual alias approved); methodology-based measurement qualification APPROVED (no universal RSE cutoff; a missing RSE is documented and does not by itself invalidate a measurement when the publisher gives none for that statistic); an auditable reviewer appointment and qualification workflow APPROVED (only a named, authenticated human may exercise reviewer authority); controlled batch qualification APPROVED where governance permits (never automatic); the broader-group rule re-affirmed; the five BLS aggregates stay quarantined; RB-LIC-1 stays open. Dossier: POLICY-H, I, J (and A to G).

## 2. Reviewer requirements (from the existing authority model, nothing new)
Authority is the code-defined platform role preset (`admin_permissions.ROLE_PRESETS`). Authentication is the existing API layer (`require_permission`). Appointment is the existing two-person role change (`RoleChangeService`). This wave added only the review service on top.

| Role | What it may do | Required (current database state, re-read on every call) | Separation of duties |
|---|---|---|---|
| A. Measurement Qualification Reviewer | decide validated measurement batches; revoke or correct them | an ACTIVE account whose current role holds `platform.knowledge.approve` (today: `knowledge_admin` or `platform_admin`) | may also be role B |
| B. Occupation Alias Reviewer | decide aliases one at a time with an evidence attestation; revoke | same permission | may also be role A |
| C. Product Owner / Release Approver | future runtime approval (not implemented here) | `platform.knowledge.approve` AND `platform.releases.read` (today only `platform_admin`) | **must differ from the batch's measurement reviewer** (`assert_separation_of_duties`) |

Required identity fields: the user id of an active account (never free text); audit rows carry actor id, request id, timestamp, decision, scope, counts and the validation digest, never record values or personal data.

## 3. Can an existing authorised human account perform the review?
- **Isolated database:** 0 accounts (nothing exists to appoint).
- **Developer database (read-only, role and status COUNTS only, no identity, email or secret read):** active accounts by role: platform_admin 1, knowledge_admin 1, billing_admin 1, operations_admin 1, security_privacy_admin 1, support_operator 1, user 5. By current role, 2 accounts could serve as reviewer A or B and 1 as release approver C.
- **Whether those accounts are real, named humans (rather than seeded test accounts) is NOT VERIFIED.** The production environment was not inspected. The owner must confirm. Until a named human accepts, appointments are **not complete**.

## 4. Reviewer appointment: the exact actions needed
Prepare (done): the role requirements above and the checklist below. Perform (needs an authenticated owner action, NOT performed): for each reviewer, an administrator who holds `platform.users.role.assign` requests the role change to `knowledge_admin` (or `platform_admin` for C) through the existing two-person role-change request; a **different** administrator holding that permission approves it (the role-change workflow's own controls apply); the target may be neither requester nor approver.

| Appointment | Named human | Role requested | Requested by | Approved by (different admin) | Accepted by the named human | Date |
|---|---|---|---|---|---|---|
| A. Measurement Qualification Reviewer | _blank_ | knowledge_admin | | | | |
| B. Occupation Alias Reviewer | _blank_ | knowledge_admin | | | | |
| C. Product Owner / Release Approver | _blank_ | platform_admin | | | | |

## 5. Making the workflow usable by a human (owner action)
`QualificationReviewService` (`src/knowledge_foundation/qualification_review.py`) exposes `validate_batch`, `decide_batch`, `revoke_batch`, `decide_alias`, `revoke_alias`. It never authenticates; it must be called with the verified principal's user id from a permission-gated admin route. **No route exists yet:** adding the five endpoints (read the review packet, decide batch, revoke batch, decide alias, revoke alias) under `require_permission(KNOWLEDGE_APPROVE)` with step-up is a privileged new surface and is the first owner decision below. A supervised shell session cannot authenticate the reviewer and is not an acceptable substitute. For production wiring, pass `reviewer_check_for(...)` to `CompensationStoreV2` and `AliasStore` so even the low-level `qualified` transition demands an active reviewer (the default trusts the caller, as before).

## 6. Deterministic measurement-review criteria
Passing engineering checks does NOT qualify a record; it only makes it eligible for review. Dimensions are kept apart:
| Dimension | Deterministic rule (code: `us_qualification.review_record`) |
|---|---|
| Source integrity | the staged file's SHA-256 matches the manifest; archive hash recorded on the record |
| Source approval | source `approved_for_ingestion`, licence `verified` (never runtime approval) |
| Occupation identity | canonical SOC 2018 node; level agrees with the published structure; non-canonical aggregates quarantined |
| Measurement validity | positive reported value; measure, pay period, gross basis, USD known; `*` absent, never zero |
| Published methodological limits | wage concept (straight-time gross, excluding premium pay), population (employees; self-employed excluded), national cross-industry scope, May 2025 reference, BLS annual derivation noted |
| Statistical uncertainty | published RSE preserved; descriptive distribution reported; **no cutoff**; missing RSE for median and percentiles is recorded as a limit on the claim (no precision statement), not as invalidity |
| Provenance completeness | publisher, dataset, edition, archive hash, member, sheet, source rows, field, batch, RSE and employment present |
| Evidence specificity | C1 detailed, C2 broad, from the actual level; never from publisher authority |
| Qualification approval | `qualified` only by a verified reviewer through the service |
| Runtime authorisation | separate; none requested |

## 7. Reliability methodology (for the reviewer's decision)
BLS publishes a relative standard error (PRSE) for employment and for the mean wage and defines it as a measure of model error; it publishes none for the median or percentiles. The May 2025 technical notes describe the estimates as model-based (MB3). Proposed methodology (a recommendation, not a decision): qualify each measure for what it is (identity, definition, provenance); never state precision beyond what BLS publishes; show the mean's PRSE whenever a mean is shown; never display a median or percentile as more precise than "BLS-published estimate"; revisit with a reviewer-adopted rule if the product later wants ranges or comparisons. **No measurement lacks a defensible qualification claim under this method, so none is held back for a reliability reason;** if the reviewer rejects the method, the affected groups stay pending.

## 8. Measurement review packet: batches (16,140 records, partitioned without loss)
Edition: OEWS May 2025 national (all groups); reference period May 2025; archive `oesm25nat.zip` (hash in the manifest); transformation `p10c-f2a-oews-national-1`.

| Group (level/pay period/measure) | Records | Engineering-checked | Exceptions | Class | Uncertainty data | Digest (first 12) | Route |
|---|---|---|---|---|---|---|---|
| detailed/annual/mean | 813 | 813 | 0 | C1 | mean RSE published | `020dda193f8d` | batch review with sample confirmation |
| detailed/annual/median | 813 | 813 | 0 | C1 | no BLS RSE for this statistic | `7eba90a3a245` | batch review with sample confirmation |
| detailed/annual/percentile | 3,252 | 3,252 | 0 | C1 | no BLS RSE for this statistic | `d49fae73c8e3` | batch review with sample confirmation |
| detailed/hourly/mean | 762 | 762 | 0 | C1 | mean RSE published | `f02b15d32e60` | batch review with sample confirmation |
| detailed/hourly/median | 762 | 762 | 0 | C1 | no BLS RSE for this statistic | `51cb0db2c52c` | batch review with sample confirmation |
| detailed/hourly/percentile | 3,048 | 3,048 | 0 | C1 | no BLS RSE for this statistic | `32ab46cb6d23` | batch review with sample confirmation |
| broad/annual/mean | 568 | 568 | 0 | C2 | mean RSE published | `3df047826da4` | batch review with sample confirmation |
| broad/annual/median | 568 | 568 | 0 | C2 | no BLS RSE for this statistic | `f6b129f2f7f6` | batch review with sample confirmation |
| broad/annual/percentile | 2,272 | 2,272 | 0 | C2 | no BLS RSE for this statistic | `4bfb3620492b` | batch review with sample confirmation |
| broad/hourly/mean | 547 | 547 | 0 | C2 | mean RSE published | `93b2d8cfe76c` | batch review with sample confirmation |
| broad/hourly/median | 547 | 547 | 0 | C2 | no BLS RSE for this statistic | `6205d5c680f7` | batch review with sample confirmation |
| broad/hourly/percentile | 2,188 | 2,188 | 0 | C2 | no BLS RSE for this statistic | `9ff9cc8ab81f` | batch review with sample confirmation |

**Ready for human approval:** all 12 groups (every record engineering-checked, zero exceptions, single evidence class, methodology complete). **Records requiring exceptions or individual assessment: 0 today.** Special attention (inside the groups, sampled for explicit confirmation): the 7 duplicate-presentation occupations (one observation each, both source presentations in provenance). **Not records and not in any batch:** the 5 quarantined BLS-specific aggregates. Missing methodology: none. Conflicts: none. Each group lists 3 representative source records (code, field, source rows, hash) in the packet. A batch decision binds to the digest, so any change to the data or state invalidates it.

## 9. Alias evidence review (engineering recommendations; no alias is approved)
Word containment was NOT treated as sufficient: each review reads the official definition of the target and of the competing SOC occupations. Full text excerpts are in the packet.

| Market title | Target | Relationship | Competing SOC occupations | Overbroad risk | Recommendation | Conditions |
|---|---|---|---|---|---|---|
| Software Developer | 15-1252 Software Developers | exact | 15-1251 Computer Programmers, 15-1253 Software Quality Assurance Analysts and Testers, 15-1254 Web Developers, 15-1299 Computer Occupations, All Other | low | **APPROVE_RECOMMENDED** | none |
| Human Resources Manager | 11-3121 Human Resources Managers | exact | 11-3111 Compensation and Benefits Managers, 11-3131 Training and Development Managers, 11-1021 General and Operations Managers | low | **APPROVE_RECOMMENDED** | none |
| Sales Manager | 11-2022 Sales Managers | exact | 11-2021 Marketing Managers, 41-1012 First-Line Supervisors of Non-Retail Sales Workers, 41-1011 First-Line Supervisors of Retail Sales Workers | low to moderate | **APPROVE_RECOMMENDED** | none |
| Accountant | 13-2011 Accountants and Auditors | narrower | 13-2082 Tax Preparers, 13-2081 Tax Examiners and Collectors, and Revenue Agents, 43-3031 Bookkeeping, Accounting, and Auditing Clerks | moderate | **CONDITIONAL_APPROVAL_RECOMMENDED** | every answer must carry the scope caveat that the figure is for Accountants and Auditors combined (implemented through the alias limitation text) |
| Financial Analyst | 13-2051 Financial and Investment Analysts | context_dependent | 13-2031 Budget Analysts, 13-2041 Credit Analysts, 13-2054 Financial Risk Specialists, 41-3031 Securities, Commodities, and Financial Services Sales Agents | moderate to high | **CONDITIONAL_APPROVAL_RECOMMENDED** | every answer must carry the scope caveat naming Financial and Investment Analysts and the excluded neighbouring occupations; the reviewer decides whether the alias may be the default reading of the bare title or must require investment/valuation context; if neither is acceptable the title should be treated as ambiguous |

**Sufficient supporting evidence:** Software Developer, Human Resources Manager, Sales Manager (approve-recommended); Accountant and Financial Analyst only with their scope caveats (conditional). Every alias is US-scoped (the resolver now ignores a country-scoped alias for any other or unstated country), carries its relationship and caveat (shown in the answer's coverage limitations), and is revocable.

### Unresolved titles
| Market title | Identity status | Candidate SOC occupations (official definitions read) | Recommendation | Safe behaviour |
|---|---|---|---|---|
| Data Analyst | multiple_candidate_occupations | 15-2051 Data Scientists, 15-2041 Statisticians, 15-2031 Operations Research Analysts, 13-1111 Management Analysts, 15-1211 Computer Systems Analysts, 13-1161 Market Research Analysts and Marketing Specialists | **AMBIGUOUS** | no alias; the resolver keeps returning not_found; a product contract could ask for occupational context, which is a product decision |
| Product Manager | multiple_candidate_occupations_context_dependent | 11-2021 Marketing Managers, 11-3021 Computer and Information Systems Managers, 11-1021 General and Operations Managers, 13-1082 Project Management Specialists, 11-9199 Managers, All Other | **INSUFFICIENT_EVIDENCE** | no alias; abstention preserved |

No mapping is created for either title; no approved source supports a unique occupation; nothing was downloaded to look for one.

## 10. Persistent-registry transition plan (future, needs owner authorisation; nothing performed)
1. Owner or an authorised administrator records the Package 1 ingestion approval for `us_soc_2018` and `bls_oews` in the persistent registry through `SourceRegistry` (discovered, licensing_pending, licence verified, licensing_verified, approved_for_ingestion), each transition audited with the owner reference.
2. A backed-up, separately authorised import into the persistent database (the isolated run is the rehearsal; the manifest hashes and the transformation id make it reproducible).
3. Reviewer decisions (this package) are repeated in that database by named reviewers; digests will differ.
4. Runtime approval is a separate decision by role C after: qualified measurements and aliases, a recorded `validation_status`, RB-LIC-1 resolved, runtime wiring approved.
5. Revocation at any point: batch and alias revocation here; `restricted` for the source. Nothing is deleted.

## 11. What remains blocked by licensing (RB-LIC-1)
Legal question for a qualified reviewer: *may Ask4Mo store, transform and commercially present BLS OEWS statistics and 2018 SOC content to candidates and customers in each non-US market where it operates?* Source evidence: the BLS copyright page says publications are in the public domain except previously copyrighted photographs and illustrations, asks that BLS be cited as the source, and prohibits unauthorised use of the BLS emblem; it does not address commercial use; the SOC page carries no reuse statement and links the BLS copyright page. Whether US public-domain status carries to other jurisdictions is a legal matter this package does not decide. Closing it needs a written legal opinion (and optionally a BLS statement). Independent offline validation was not blocked by it; candidate-facing deployment is.

## 12. Owner actions needed to complete qualification, in order
1. Decide whether to authorise the five privileged admin endpoints (section 5) and who implements them.
2. Name the three people; run the two-person role changes; record acceptances (section 4).
3. Reviewer A reads section 6 to 8, validates and decides the 12 batches (or rejects any).
4. Reviewer B decides the five aliases individually; decide what to do with Data Analyst and Product Manager.
5. Close or accept RB-LIC-1 for the target markets.
6. Only then: persistent-registry steps (section 10) and a separate runtime-activation decision.

## 13. Actions that need a future runtime-activation decision
Runtime wiring and activation of Compensation V2; any candidate-visible use of qualified evidence or aliases; presentation of contextual broader-group evidence; runtime approval of a source in the registry; any international comparison. None is authorised or performed.
