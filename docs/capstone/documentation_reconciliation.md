# Documentation Reconciliation (P0/E0 findings, resolved in P1)

P0/E0 catalogued documentation contradictions. This is the bounded reconciliation
pass (§17 of the P1/E1 brief). It records each item, classifies it as **CURRENT**,
**HISTORICAL** or **SUPERSEDED**, and states the resolution. Truthful historical
evidence is **not** rewritten to look cleaner — where a historical document contains a
claim that is inaccurate as *current* guidance, a correction note points here instead.

| # | Contradiction | Classification | Resolution |
|---|---|---|---|
| 1 | `post_release_product_surface_audit.md`: "no Agent runtime changed" — but the capability toggle changes bound tool schemas/execution (`nodes.py`/`registry.py`). | HISTORICAL (accurate for most of that audit; the phrase is imprecise) | Correction note added at the top of that doc pointing here; the capability toggle **does** alter bound tool schemas and tool-node execution. Original evidence left intact. |
| 2 | Test totals disagree across docs (1928/155/51 vs 2137 vs 2145/166/57 vs 176 fe). | HISTORICAL (each true at its time) | `CLAUDE.md` now says **always re-measure** and cites the current P1 totals (backend 2220 passed / 3 skipped; frontend 183). Historical numbers are left as period evidence, not defects. |
| 3 | `/evaluation/latest` reads `evaluations/ragas/runs/*/results.json`, not the committed `deterministic_baseline.json` (schema mismatch). | CURRENT | Documented here: the Evaluation surface reads **generated run artifacts** (gitignored), not the committed baseline; the two have different schemas by design. A fresh clone shows an empty Evaluation surface until runs are generated. No code change in P1 (out of scope). |
| 4 | Knowledge/Evaluation "committed evidence artifacts" wording vs gitignored generated files. | CURRENT | Clarified in `p0_e0_current_state.md` and here: the diagnostics data (`roles.db`, Chroma, RAGAS runs, retrieval artifacts) is **generated and gitignored** — present in a working checkout, empty on a fresh clone. Provisioning is via the existing `scripts/check_demo_knowledge.py` / build scripts. |
| 5 | `CLAUDE.md` opened with "Modular Streamlit monolith" though Next.js+FastAPI is primary. | SUPERSEDED | `CLAUDE.md` architecture section rewritten: Next.js + FastAPI is the primary product; the Streamlit monolith is legacy over the same application layer. |
| 6 | `CLAUDE.md` identity described as a "transitional `X-User-Subject` boundary … production still needs a real gateway/OIDC". | SUPERSEDED by P1 | `CLAUDE.md` now describes real accounts (register/verify/recover/login/logout), server-side sessions, and the dev-only header. See `p1_e1_identity_platform.md`. |

## Distinctions applied
* **CURRENT** — active guidance a reader should trust today; fixed in place.
* **HISTORICAL** — accurate for the phase that produced it; preserved, with a pointer
  where it could mislead as current guidance.
* **SUPERSEDED** — replaced by later work (P1); the current doc is corrected and the
  change recorded here.

Non-blocking follow-ups (not P1 scope): a single "current evidence index" and demo-data
provisioning alongside P2 (tracked in the risk register R-3/R-10).
