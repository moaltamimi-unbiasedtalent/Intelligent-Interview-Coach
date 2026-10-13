# Ask4Mo: Knowledge Admin Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This document describes what the **knowledge_admin** role can do **today**, derived from the code-defined permission preset, the frontend destination table and the route permission graph (a read-only derivation, nothing mutated). Anything not built is labelled **PLANNED W12.4**. The role index is [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md); the owner role is [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md).

## 1. Role purpose

Govern the platform knowledge base: register sources, upload and review them, approve them, index them, activate them and retire them, and read AI-configuration and job state. **W12.4A diagnosed and fixed two root causes of the owner-reported Knowledge issue in code (working-directory-relative store paths, and Mo's agent not wired to governed knowledge); the governed part of the knowledge base still needs a source activated and a worker running in the developer environment.** Authorization is by permission string only; the role name is never checked by any route. The role is a code-defined preset and cannot be customised. It is a delegated, least-privilege operational role, not a junior Platform Admin.

## 2. Permission boundary

**6 permissions:** `platform.overview.read`, `platform.knowledge.read`, `platform.knowledge.manage`, `platform.knowledge.approve`, `platform.ai.read`, `platform.jobs.read`.

Of the 147 Admin API routes this role may call **41**: Knowledge source, version and lifecycle routes, the read-only AI configuration routes, job reads, and the Review / Diagnostics reads (knowledge diagnostics, reviewer knowledge readiness, manifest, source health, coverage and language boundary; evaluation and prompt-lab reads).

## 3. Visible navigation

**5 destinations:** Overview (`/admin`), Review / Diagnostics (`/review`), Knowledge (`/admin/knowledge`), AI and models (`/admin/ai`, read only) and Jobs (`/admin/jobs`, read only).

## 4. Typical workday / workflow

Sign in -> Overview (knowledge counts: awaiting review, indexing, failed, active) -> Knowledge: **register or upload a source** (title, publisher, https reference that is never fetched, language, authority level, licence class, provenance note) -> **scan and parse** (background jobs) -> review the bounded preview, provenance and authority -> **approve** -> **index** (background job) -> monitor the job on the Jobs page -> **activate** -> read **Knowledge readiness** and run **Test retrieval** on the Knowledge page -> inspect Review / Diagnostics. Retire a source or upload a new version when content changes.

## 5. Key actions

| Action | Permission | Notes |
|---|---|---|
| View sources, versions, preview and metadata | `knowledge.read` | |
| Register a source, upload a version, edit metadata before approval, reprocess, delete a never-approved version, request indexing, retire | `knowledge.manage` | Upload accepts PDF, TXT or Markdown; licence class "unclear" or "restricted", missing provenance or a failed or missing scan blocks approval |
| Approve, reject, activate | `knowledge.approve` | Approval and activation are separate explicit steps |
| See knowledge readiness, the active-knowledge inventory and run a retrieval-only test | `knowledge.read` | W12.4A, CURRENT: the test goes through the production retrieval boundary, calls no model and accepts only a query |
| Read AI configuration state | `ai.read` | Read only |
| Read the job queue and worker state | `jobs.read` | Read only |

**Authority levels:** 1 = official / statistical; 2 = public / professional framework; 3 = reputable industry. The seven knowledge languages apply; Russian is not a knowledge-base language and not an official ESCO language.

## 6. High-risk actions / governance

- **Unapproved content must not become candidate-retrievable.** Parsed is not approved, approved is not indexed, indexed is not active; retrieval trusts only the SQL active set and writes only to the separate governed collection. This is enforced by the service, not by the role.
- Approval, activation and retirement are audited in the same transaction. There is **no distinct-actor rule and no step-up** for knowledge approval today: one account can upload and approve (finding SJA-05).
- Nothing in this role can bypass the licence, provenance or scan gates.

## 7. What the role cannot do

Retry, cancel or queue jobs (it holds `jobs.read` only); see integrations, provider status, configuration, flags, reports or security; manage, evaluate or activate AI configurations; read users, support or billing; and read candidate data. It cannot see the integration or secret configuration that indexing and the vector store depend on.

## 8. Candidate-data boundary

| This role **can** see | This role **cannot** see |
|---|---|
| Platform knowledge text it uploaded, parse previews of that text, governance metadata, aggregate readiness and coverage | CV, documents, interview answers, Mo conversations, Story Bank, memory, reports |
| AI configuration state and job summaries (never job payloads) | Which candidate asked what; per-candidate retrieval history |

Never visible to this role (or to any Admin role, including the 43 / 43 Platform Admin): candidate CVs, raw candidate documents, interview answer text, Mo conversations, Story Bank and private evidence, private preparation memory and candidate report contents. There is no break-glass, no impersonation and no "view as user" permission.

Uploaded knowledge is **platform** knowledge, not candidate data. Candidate documents are a separate private system that this role cannot reach.

## 9. Current operational limitations

- **CURRENT - PARTIAL (W12.4A fixed two root causes in code).** The owner-reported accessibility problem was traced to (1) working-directory-relative store paths, which made an app or worker launched from another folder see an empty knowledge base (now anchored to the data root), and (2) Mo's agent not being wired to Admin-governed knowledge. **Residual operator action in the developer environment:** no governed source is registered yet and no job worker is running, so a source still has to be approved, indexed (needs `python -m src.jobs.worker`) and activated before governed knowledge appears. Knowledge is not described as fully production-operational. See `../knowledge/W12_04A_KNOWLEDGE_ACCESSIBILITY_OPERATIONS.md`.
- No retrieval-test console and no complete snapshot model; parts of the Knowledge capability are classed PARTIAL in the Admin capability matrix.
- Parse and index **depend on a worker process**; the Knowledge pages show only that work is queued, and the worker-seen warning is on the Jobs page.
- The role cannot retry a failed knowledge job (finding SJA-02).
- The Admin cannot see, from the Knowledge page, what the active knowledge base currently returns to a candidate (Platform Admin finding A-05).

## 10. Escalation to Platform Admin

Escalate to **Operations Admin or Platform Admin** for: a worker that is not running, a failed job needing retry or cancel (`jobs.manage`), provider, vector-store or credential problems (integrations, configuration), and AI configuration changes (`ai.manage` and `ai.activate` are held only by the Platform Admin). Escalate to the Security / Privacy Admin or Platform Admin for privacy or security questions.

## 11. Planned W12.4 impact

**W12.4A is implemented** (readiness, active inventory, retrieval-only test, worker hint, the two root-cause fixes). Further W12.4 sub-waves that touch this role: W12.4F may revisit whether this role needs job-retry visibility. No permission change was made.

## 12. Route reference

| Page | URL |
|---|---|
| Overview | `/admin` |
| Knowledge sources | `/admin/knowledge`, `/admin/knowledge/{id}` |
| AI and models (read only) | `/admin/ai`, `/admin/ai/{id}` |
| Jobs (read only) | `/admin/jobs`, `/admin/jobs/{id}` |
| Review / Diagnostics | `/review`, `/review/agent`, `/review/rag`, `/review/evaluation` (renders outside the Admin shell, finding F-01) |
