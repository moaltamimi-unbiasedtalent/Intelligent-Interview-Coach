# P8 Productisation & Hosting — Gap Audit

_Capstone P8. Written BEFORE implementation (as the phase mandates). Classifies every
remaining productisation/hosting requirement against the ACTUAL code state at baseline, and
lists the doc contradictions to reconcile. Status vocabulary: DELIVERED / PARTIAL / ABSENT /
UNVALIDATED / BLOCKED._

Baseline: `main` @ `32d1eeb` (P7.5 merged, PR #83); Alembic head `0011_workspaces_shares`;
branch `feature/capstone-p8-productisation-hosting`.

Hard rule carried from the acceptance package: _"Public hosting cannot be marked complete from
a local build or a deployment plan. Missing external credentials or owner approvals are
reported as Blocked, not Passed."_ → EX-12 cannot PASS in this phase.

---

## Requirement classification

| Req | Area | Baseline state | P8 target | Classification (baseline → after P8) |
|---|---|---|---|---|
| **D5** | Privacy/data controls | Export (`/auth/account/export`, user+interviews only) + soft **delete-request** (status flip, no removal); Memory/Documents/Sharing UIs exist but scattered | Coherent self-service export/delete/manage | PARTIAL → **DELIVERED** (coherent data-rights hub + full deletion cascade) |
| **D6** | Privacy/legal public surfaces | none | Privacy, Terms, AI-transparency pages | ABSENT → **DELIVERED (engineering draft; legal review required)** |
| **D7** | Public marketing website | `/` is the *authenticated* app home; no public site | Public front door | ABSENT → **DELIVERED** (`/` marketing + `/app` product) |
| **D8** | Public/app route separation | server fail-closed + client RouteGuard; but `/` = app home | Clean public/app boundary | DELIVERED → **STRENGTHENED** (marketing `/`, product `/app`) |
| **D9** | Pricing/product presentation | none | Basic/Premium presentation (no billing) | ABSENT → **DELIVERED (presentation only; billing OUT_OF_SCOPE)** |
| **C12** | Public hosting (HTTPS, verified-email reg) | no deploy artifacts; SQLite default; no prod validation | Reproducible deploy + limits + rollback | ABSENT → **READY (implementation) / EX-12 NOT RUN (needs authorized deploy)** |
| **L-mkt** | Marketing site + positioning | none | Public IA + pricing + trust | ABSENT → **DELIVERED (engineering draft)** |
| **AC-19** | Core interface readiness | app renders; no marketing; SEO minimal | render without clipping, keyboard, contrast, truthful states | PARTIAL → **PARTIAL→READY** (a11y/responsive pass this phase; full browser-matrix carried) |
| **EX-12** | Hosted operation | not run | authorized HTTPS deploy exercising reg/storage/limits/backup/rollback/pause | NOT RUN → **BLOCKED / NOT RUN** (no owner-authorized deployment) |
| localization completeness | i18n | 7-locale arch; core surfaces localized; some deep pages/Help bodies English | every normal candidate surface localized | PARTIAL → **PARTIAL** (marketing localized; bounded completion + honest review matrix) |
| auth rate limiting | security | **NONE** on `/auth/*` | per-IP/per-account bounded, anti-enumeration preserved | ABSENT → **DELIVERED** |
| provider/cost limits | security/cost | only realtime limiter (in-memory) | per-user + global + concurrency on costly ops | PARTIAL → **DELIVERED (local) / distributed store carried** |
| full account deletion | privacy | soft request only | app-controlled cascade incl. files + checkpoints | ABSENT → **DELIVERED (app-controlled; backups documented)** |
| upload malware scanning | security | content validation only (no AV) | scanner abstraction + fail-closed policy | ABSENT → **DELIVERED (abstraction + policy; live scanner carried)** |
| backup/restore | hosting | none | documented + tooling | ABSENT → **READY (documented + scripted) / hosted restore NOT RUN** |
| rollback | hosting | none | documented procedure | ABSENT → **READY (documented)** |
| operator pause switch | ops | none | bounded pause for costly features | ABSENT → **DELIVERED** |
| env validation | hosting | all loaders fail-open | prod fail-fast on missing critical config | ABSENT → **DELIVERED** |
| security headers | security | none | CSP/HSTS/etc. | ABSENT → **DELIVERED** |
| health/readiness | hosting | `/ready` == `/health` | real readiness probe | PARTIAL → **DELIVERED** |
| provider live validation | providers | email/OIDC/realtime/Adzuna all UNVALIDATED | live-gated checklist | UNVALIDATED → **UNVALIDATED (checklist prepared; not run)** |

---

## Doc contradictions to reconcile (§2)

1. **i18n scope** — matrix `Explicit OUT_OF_SCOPE` still lists _"whole-app UI translation"_, and `00_Expanded_Project_Plan.md` says _"full application-copy translation is a separate decision"_ / _"Whole-application UI translation is not implied"_. **Superseded**: the owner later made seven-language internationalization/localization a Capstone deliverable (P3.5 + this phase). → Update scope truthfully, preserving the decision history (scope was *expanded*, not rewritten).
2. **C8 model policy** — Group I row still says `PARTIAL (registry)`, but P5/E4 evidence shows the central per-operation policy DELIVERED (`src/llm/policy.py`, now 8 operations incl. REALTIME_VOICE). → Update C8 to DELIVERED (per-operation policy), gate EX-09 still Not run.
3. **K1–K4** — marked `DELIVERED (P6)` while gates EX-13–16 remain `Not run`; K1 figures "engineering-draft", K2 legal "carried", K4 "live UNVALIDATED". → Keep DELIVERED-as-code but ensure no summary implies data/legal/live validation. Add an explicit note.
4. **Audio privacy** — some older privacy/architecture text may describe persisted audio/recordings. P7/P7.5 store **no** Ask4Mo audio. → The Privacy page and current-architecture docs must distinguish historical/target concept vs actual released behaviour, and must NOT claim audio is stored.
5. **AC-25 routing** — matrix routes D6/D7/D9/L-mkt to AC-25 ("submission consistency"), whose text doesn't test privacy/terms/marketing/pricing; no AC covers HTTPS/hosting (only EX-12). → Note this; classify these against their actual delivery + EX-12, not a mismatched AC.
6. **Totals line** — `PARTIAL ≈ 12 · ABSENT ≈ 22` is the stale P0 snapshot. → Mark it explicitly as the P0/E0 baseline snapshot (not current).

---

## Critical implementation notes discovered

- **SQLite FK cascades don't fire** (no `PRAGMA foreign_keys=ON` in `make_engine`), and several user-owned tables are **not** ORM-cascaded from `User` (`interview_sessions`, `candidate_documents`+children, `candidate_stories`+`story_evidence`, all workspace/share tables). → The deletion orchestrator must delete these **explicitly, in child→parent order**, not rely on `session.delete(user)`. (Enabling the PRAGMA globally mid-phase risks the 2369-test suite; carried as a recommendation.)
- **Agent checkpoints** have no bulk-by-user purge API; `thread_id == run_id`, owner `user_id` lives in checkpoint state (string). → Purge per tracked `run_id` (discoverable via `PreparationMemory.source_run_id`); untracked-run checkpoints are a documented residual pending a saver-level/prod purge.
- **Workspaces**: owner deletion currently cascades (DB) — decision for P8: **transfer to another active owner where one exists, else delete the workspace** (revoking members' shares first), so co-members aren't silently stripped without record.
- **Audit** rows must be **anonymized (SET NULL), not deleted** (security retention), plus a final `account.deleted` audit event.
- **Malware scan seam**: after `validate_upload`, before `DocumentStore.save` (`documents_service.py`).

---

## Verdict
Everything except live-provider validation and actual hosted operation (EX-12) is buildable and
testable locally in this phase. EX-12 remains **BLOCKED / NOT RUN** pending explicit owner
deployment authorization; provider live validations remain **UNVALIDATED** (checklist prepared,
not run). Public deployment is **NOT AUTHORIZED** by this task.
