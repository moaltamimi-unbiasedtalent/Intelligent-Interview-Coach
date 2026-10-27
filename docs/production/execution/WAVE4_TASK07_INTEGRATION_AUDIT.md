# Wave 4 Task 07 — pre-change integration audit

Authoritative baseline: PR #272 merge `992682c3fa9c891f5710c993e7d595f363b8c811`.
All seven post-merge workflows passed (CI 40247207939, Redis 40247207906,
migration 40247207971, recovery 40247207860, admission 40247207903,
budget 40247207914, images 40247207972). Browser is PR/on-demand.

Preservation inventory: 45 worktrees, 312 existing branches, 49 protected file
hashes and the original untracked artwork. No original database is opened for
integration tests. The original SQLite remains at its last observed 0027.
Local Docker overlay is 99% used, with 644 MB free; unrelated running services
must remain untouched. The existing immutable-image workflow can run the actual
campaign using its own freshly verified images; local full-stack execution must
refuse insufficient capacity rather than prune shared resources.

| Area | Existing component | Integration disposition |
|---|---|---|
| Images/topology | release_images profile + qualified recovery derivative | Reuse the verified API/web/operator images and Compose services; unique disposable project/network/volumes. No publication. |
| Startup | one-shot migrate, API/worker success dependencies | Observe real startup, schema head, worker presence and restart; inject migration failure without changing production startup. |
| Redis | qualified ACL script/client + private internal network | Reuse exact policy/namespace configuration. Exercise shared/outage behavior; no H-REDIS-POLICY approval. |
| Scanner | official clamd TCP adapter; original topology downloads definitions | Run a real daemon on an internal network with a harmless offline EICAR test-signature fixture. Report signature freshness/coverage as unqualified; no external corpus/model downloads. |
| Edge | Caddy staging CORS/cookie/CSP topology | Local internal certificates, loopback-only TLS, reserved example hostnames with local resolver rules, no ACME/public DNS. Preserve security headers. Test hydration and record failures rather than weaken CSP. |
| Identity | invitation-only registration, real sessions, memory email adapter | Synthetic accounts/invitations and private in-memory mail capture; no email delivery. Preserve authentication/ownership and expiry rules. |
| Language | zero approved hosted languages | Strict staging must reject registration and new language-bearing AI/interview activity. No record/guard override, no fabricated approvals. Positive flows blocked by this boundary are NOT RUN, not PASS. |
| Existing journey launcher | real FastAPI/Next journey with LA.current override | Reuse fixtures/contracts where appropriate, never its staging language override. The new campaign must not claim that bypass as hosted qualification. |
| AI | offline provider guard + capability-2 monetary governor | No provider credential, no owner-approval marker. Test missing-approval refusal and deterministic isolated service/ledger fixtures; separate them from HTTP flows blocked by language/budget policy. |
| Worker/agent | real Worker/JobService, durable PG checkpoints and admission | Independent instances; real diagnostic jobs, crash/lease/idempotency probes and scripted model fixtures. Label direct-service evidence precisely. |
| Recovery | existing qualified PG16 engine/operator image | Capture/transfer/new-target restore, independent erasure head and persistent hold; never clear hold to force a happy path. |
| Evidence | prior isolated subsystem workflows | Add connected campaign to existing image CI, retain those workflows. Structured PASS/FAIL/SKIP/NOT RUN, safe logs and mandatory failure exits. |

Campaign success is engineering evidence only. A functional failure remains FAIL;
an explicit owner-policy dependency remains NOT RUN. Serious/high-risk defects
are reported for focused follow-up, not hidden behind relaxed assertions.
R1.0 remains 40/45; 00A/00B/07B/07C/08A, PG/LG acceptance and hosted decisions
remain open. No deployment, real emails/data, paid calls, approval-marker creation,
registry publication, broad cleanup or automatic merge is authorized.

## Confirmed pre-campaign defect POST272-01

A fresh named volume mounted at `/data/knowledge` on existing API image
9237c43d0795 was owned by UID 0 and not writable by application UID 10001.
The same directory-creation line is unchanged in the authoritative Dockerfile.
The API image creates/chowns `/data/documents` but not the knowledge mount point.
Minimal repair: create both paths before the existing recursive app-user chown.
No runtime root execution or original-volume permission modification is introduced.
The connected campaign must verify the newly built image with fresh named volumes.
The labelled reproduction volume was removed; existing images/services remain.

## Confirmed pre-campaign defect POST272-02

Installing the existing offline network guard and a CLOSED hosted budget governor
in one process raises `guard_conflict`, preventing safe non-AI API/worker startup.
Reproduced without any network request or credential. Minimal repair permits only
CLOSED-governor + offline-guard layering; open/live guard conflicts remain refused.
Both refusal layers remain installed. Regression coverage must prove zero transport
calls for external/provider requests and working local non-AI requests.

## Reconciliation preservation audit — 27 October 2026

Before modifying any checkout: 48 worktrees inspected (31 with existing local changes), 316 branch tips recorded, and 200 protected/untracked files hashed. The private inventory includes ignored-status records for each available checkout, unpublished branch tips, environment/secret files, original databases and artwork. It remains outside Git at `/private/tmp/ask4mo-requal-preservation.json`; no contents or credentials are published. Original SQLite is not opened or migrated; its last observed revision remains 0027, not newly verified by a database connection.

Original PR #273 tip `bc75b4c772e5468934d033fe565eac5b921e4927` is retained by `refs/backup/task07-before-reconciliation-20261027`. A detached candidate checkout preserves the permanent checkout and branch until qualification. Normal merge of verified main `ef2e97ef88b4f4b67640c4c677f3ef3247594cd2` retains both parents. Two textual conflicts: immutable workflow retains both CSP and connected campaigns with separate safe evidence uploads; release tracker retains dated historical blocks and adds an explicit current-state header. Dashboard auto-merged and received the same current-state distinction. All reviewed CSP/checkpoint/History production implementations remain byte-identical to main; only previously reviewed Task 07 startup repairs differ in application/deployment code.

The connected checkpoint regression now verifies both API reads before/after the outage, unchanged container/start/restart identities and zero model calls. The old explicit API restart fallback is removed; mandatory recovery failure stays FAIL. Connected browser coverage adds real History/Opportunities reads, image loading, secure session flags, unauthorized inline injection refusal and UI logout. Linux qualification uses a temporary candidate ref; the existing PR branch must not advance before successful qualification. Historical 27/2/6 evidence and all gate approvals remain unchanged.

## Verified candidate outcome — 27 October 2026

Normal merge candidate `939b7f020609850a56cf5b15cbcefb6ec328c284` passed all eight workflows, including actual immutable images and the full connected campaign (29 PASS / 0 FAIL / 0 SKIP / 6 owner/hosted NOT RUN). Both original APIs read their checkpoints before/after PostgreSQL restart without process restart or model replay. Primary Browser: 672 passed / 14 skipped, plus 50 History repeats at zero retries. Full backend: 8,726 passed / 181 skipped, 8,907 reconciled. Current [source-bound report](WAVE4_TASK07_INTEGRATION.md) and structured evidence append these results without replacing the historical 27/2/6 snapshot.

Preservation recheck before promotion: all 200 protected hashes, all 48 original worktree statuses and all 316 original branch tips unchanged. Private inventory SHA-256: `fd01c514833dd7ef9432d945a6ecec4cd2a7001f8406e40c945a8b067ab9a6be`. After qualification, only the authorized Task 07 branch/checkout is advanced by fast-forward; every unrelated branch/worktree/file remains protected. Original SQLite is not opened or migrated. The candidate worktree and qualification ref are retained. No deployment, registry publication, gate approval or automatic PR merge is performed.
