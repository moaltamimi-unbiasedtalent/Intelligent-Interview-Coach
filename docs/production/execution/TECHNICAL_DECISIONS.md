# Technical Decisions (options only; none is decided)

**Status:** PROPOSED options for owner decision, 2026-10-21. Nothing is provisioned, purchased or configured. Each section lists realistic options with trade-offs and a **recommendation labelled PROPOSED**. Prices, regions and vendor terms are not asserted because they were not verified in this phase: checking them is part of the decision. Every option must satisfy the fixed constraints: free private beta, no live payments, EU data-protection posture, owner-operated Admin, fail-closed security defaults.

## Constraints that bound every option

R1.0 is a free invitation-only beta (small user count, unknown but low). The stack already runs as FastAPI + Next.js + PostgreSQL-capable SQLAlchemy with a DB-backed queue and a separate worker, Chroma for vectors, a documents volume for private files, and Caddy for TLS (`deploy/`). Single-replica limits are documented (EX-12 #15). Any option that needs a new runtime dependency adds a package, a deployment unit and a test burden inside a five-week window.

## D1 Hosting (OD-HOSTED)

| Option | For | Against |
|---|---|---|
| A. One EU VPS running the existing Docker Compose topology behind Caddy | Matches `deploy/docker-compose.staging.yml`; lowest change; clear data residency; cheapest | Owner operates the host (patching, backups, uptime); single point of failure; manual scaling |
| B. Managed container platform in an EU region (web and API as services, managed PostgreSQL) | Less operations work; built-in TLS and deploy history | Persistent volumes for private files and Chroma may be limited or costly; platform lock-in; need to verify worker and volume support |
| C. Major cloud (container service plus managed database and object storage) | Strong managed building blocks; mature backup and monitoring | Highest setup effort and cost for a beta; most configuration to learn |

**PROPOSED:** A for the beta (smallest change from the verified topology), with the restore drill (05B) proving recoverability, and a documented path to B or C if the beta grows. Needs OD-HOSTED: provider, region, domain, who operates it, and approval to create staging and production.

## D2 PostgreSQL

| Option | For | Against |
|---|---|---|
| A. PostgreSQL 16 container in the same Compose stack (current staging design) | Simple; one backup scope with files | Operated by the owner; backups and upgrades are manual |
| B. Managed PostgreSQL in an EU region | Automated backups and point-in-time recovery; patching handled | Extra cost; network latency; connection limits |

SQLite is used in development and tests only; the register lists PostgreSQL-only paths (job claim with SKIP LOCKED, audit trigger DDL, managed secrets) as untested live (R-96a, R-96b, H-PG-SECRETS). **PROPOSED:** B if budget allows, otherwise A with scripted dumps; either way 05B must exercise those paths on a disposable PostgreSQL before launch.

## D3 Persistent file and vector storage

| Question | Options | Notes |
|---|---|---|
| Private uploaded files (candidate documents, governed source files) | A. Local volume with encrypted disk and backup; B. EU S3-compatible object storage with server-side encryption | A is what exists (`documents` volume); B improves durability and separate backup but needs an adapter |
| Governed and curated vector indexes | A. Chroma on a persistent volume, rebuilt from approved sources when needed; B. pgvector inside PostgreSQL (single backup/restore story); C. managed vector service | A needs the missing knowledge volume (gap G1) and manifest verification; B simplifies restore but is a retrieval-layer change; C adds a processor of candidate-adjacent data |

**PROPOSED:** keep Chroma (A) for R1.0 because the retrieval stack is built on it, add the persistent volume, manifest checksums and a rebuild command (02A, 02B), and record pgvector as an R1.1+ simplification to evaluate. Files: A for R1.0 with encrypted disk, B evaluated later.

## D4 Embedding provider (OD-EMBED)

The current default silently falls back to a lexical hash embedder; REVIEW-04 requires a real semantic embedder in production or a fail-closed refusal. The existing code treats `COPILOT_EMBEDDING_API_KEY` and `COPILOT_EMBEDDING_PROVIDER=openai` as the semantic path, and notes OpenRouter does not serve OpenAI embeddings.

| Option | For | Against |
|---|---|---|
| A. OpenAI embeddings (`text-embedding-3-small`) directly | Already coded and priced in the demonstration ledger; strong multilingual | Data processed by a US provider (needs DPA and K-PROVIDER review); paid, needs budget |
| B. EU-hosted OpenAI-compatible endpoint (for example a cloud-provider OpenAI service in an EU region) | Better residency story | Availability and terms to verify |
| C. Self-hosted multilingual model (for example an open multilingual embedding model) on the host | No third-party data processor; fixed cost | CPU or GPU sizing, model licence review, quality must be measured for all seven languages, operational burden |
| D. Keep the lexical embedder in production | No cost | Rejected by REVIEW-04 (not semantic) |

**PROPOSED:** evaluate A against C on a frozen seven-language retrieval set (02E, 06D) before choosing; until the owner decides, production mode refuses the hash embedder and development mode stays clearly labelled. Any paid build or evaluation runs through the AI spend guard (D8).

## D5 Background processing

The jobs system is a database-backed queue with a separate worker and lease-based idempotent handlers; no Celery, Redis or broker. **PROPOSED:** keep it for R1.0 (proven, tested, PostgreSQL SKIP LOCKED path to verify in 05B), run the worker as its own Compose service with health and heartbeat alerts (gap G1), single replica. Adding a broker is rejected for R1.0 (new failure modes, no need at beta scale). Redis remains only for the optional shared rate-limit store, whose live validation is J-REDIS (05D).

## D6 Malware scanning (decided by the owner: real fail-closed ClamAV)

| Option | For | Against |
|---|---|---|
| A. ClamAV daemon as a Compose service with the existing adapter completed and signature updates | Self-hosted, no data leaves the host; adapter seam and `FILE_SCAN_PROVIDER=clamav` already exist | Memory footprint; must monitor signature age; a stub today (G2) |
| B. Managed scanning API | Less operating work | Uploads leave the platform: a privacy and DPA problem for candidate documents |
| C. No scanning | none | Rejected: fail-closed scanning is an owner requirement |

**OWNER-APPROVED direction (Phase 00 sign-off): A, real fail-closed ClamAV scanning.** Fail closed when the daemon or signatures are unavailable; refuse the fake scanner outside development; EICAR test in a dedicated CI job.

## D7 Monitoring and alerting

The product has in-app alerts, an Observability seam (NoOp default, optional Langfuse for sanitised AI traces) and readiness endpoints; there is no external paging (deferred to R1.2) and no production monitoring (H-MONITOR). **PROPOSED minimal R1.0 set:** (1) an external uptime check on `/api/health` and the web root with email alerts to the owner; (2) an error tracker or structured log shipping with alert rules for 5xx rate, worker heartbeat loss, indexing failure, scanner down, signature age and backup failure; (3) the in-app Admin alerts already built; (4) an AI spend alert at 50, 80 and 100 percent of the budget. Tool choice (a hosted error tracker, a self-hosted metrics stack or the host provider's built-ins) needs the owner's cost and residency view; none is provisioned.

## D8 AI budgets (OD-BUDGET)

The capstone built a separate EUR 10 ledger with atomic reservation, per-category caps, an operating stop and a kill switch (`src/demo_live`). Production needs the same property for beta users and evaluation.

| Option | For | Against |
|---|---|---|
| A. Generalise the existing guard into a production budget governor (per environment, per feature category, per user, hard cap, kill switch) | Proven approach, tested with mocked providers; fails closed | Needs per-user accounting design and operator tooling |
| B. Provider-side credit limits only | No code | Delayed usage reports; no per-feature or per-user control |
| C. Both | Defence in depth | Slightly more setup |

**PROPOSED:** C. Budget values, categories and per-user limits are owner decisions (OD-BUDGET); the capstone authorization is not reusable. Reconcile model identities first (gap G4).

## Decisions required before Phase 01 starts

OD-HOSTED (D1, D2, D3), OD-BUDGET (D8 and any paid embedding evaluation), OD-GATE-THRESHOLDS (for 01A) and OD-RESOURCE (who works on it) before their packages, OD-EMBED (D4) before 02B. Already resolved by the owner: OD-SCOPE-01 (S1), OD-MALWARE (ClamAV), OD-INVITE (single-use invitations), OD-ADMIN-NAV (six groups). Phase 01 packages 01A, 01B and 01C need no infrastructure decision and can start as soon as the owner approves Phase 00.
