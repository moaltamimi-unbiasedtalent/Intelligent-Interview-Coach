# P9 Release-Candidate Quality Register

_The single canonical open-item register for the release candidate. Every carried item is
classified by severity so gaps are not treated as equally serious. P9 cannot PASS with an open
P0/P1 defect (see §Defects); it can carry BLOCKER-FOR-PUBLIC-LAUNCH and NON-BLOCKING items._

Severity for open items: **B10** = blocker for P10 · **BPL** = blocker for public launch ·
**NBL** = non-blocking Capstone limitation · **OPT** = optional validation.

## Carried open items

| Item | Class | Why / status | Closes when |
|---|---|---|---|
| EX-12 hosted deployment | **BPL** | implementation READY; can't be certified locally | authorized HTTPS deployment exercises reg/storage/limits/migration/backup/rollback/pause |
| EX-02 live realtime round-trip | OPT / BPL | deterministic PASS; no realtime key | authorized realtime provider + smallest EN+DE run |
| Live Google OIDC | OPT / BPL | implemented; disables cleanly unconfigured | configured client + owner-authorized live sign-in |
| Live transactional email | **BPL** | Brevo adapter ready; open registration needs it | configured Brevo + a real verification round-trip (EX-07) |
| K1 / K2 human data review | **BPL** | figures engineering-draft; abstention deterministic | subject-matter + legal review of datasets |
| K4 live Adzuna | OPT | deterministic contract PASS; test skipped (no creds) | `RUN_ADZUNA_INTEGRATION=1` + creds |
| Model-judged RAGAS | OPT | harness/fixtures validated; no paid judge | authorized paid judge run |
| Live OCR quality | OPT | deterministic fixtures PASS | live OCR engine sample |
| Live speech/TTS quality | OPT / BPL | configured + deterministic | human voice-quality review (AC-23 live) |
| Live multilingual Mo quality | OPT | deterministic routing/geo-separation PASS | live provider + human review |
| Live multi-agent/provider quality | OPT | deterministic policy/routing PASS | live comparative benchmark (AC-22 live) |
| Human translation review (7 locales) | **BPL** | engineering-draft translations, key-parity enforced | professional review |
| Legal review (Privacy/Terms) | **BPL** | engineering drafts with visible banners | legal counsel review |
| Distributed rate-limit store | NBL | single-process limiter; correct for single replica | multi-replica deployment adds shared store |
| Untracked checkpoint deletion residual | NBL | tracked run-ids purged; untracked rely on saver/prod purge | saver-level bulk purge or run-id index |
| CSRF posture | NBL | SameSite=Lax + OIDC state; no double-submit token | add token if a cross-site risk is identified |
| Deep-page localization debt | NBL | candidate flows localized; marketing legal bodies + reviewer/admin English intentional | see `p9_localization_completeness.md` |
| `product-surfaces` review/rag flake | NBL | 20/20 in isolation; 1/30 only under stressed batch → ENVIRONMENT; monitored | re-classify if it reproduces in isolation/CI |
| `PRAGMA foreign_keys=ON` (SQLite) | NBL | deletion uses explicit deletes; recommendation only | enable + re-verify suite |
| Full browser matrix (Firefox/WebKit) | NBL | Chromium FULLY TESTED; others documented | add Playwright projects when tooling permits |
| A5 knowledge-readiness distinction / A6 owned-run list / A8 selected-run RAG | NBL | partial diagnostics surfaces | future review-surface work |
| B2–B3 durable profile / opportunities | NBL | partial | future product work |

## Defects found in P9
| ID | Severity | Surface | Repro | Fix | Regression test | Status |
|---|---|---|---|---|---|---|
| (none) | — | — | integrated journeys + security + recovery exercised | — | — | **no P0/P1/P2 defects found** |

The P8 CI issues (stale tutorial mock; evaluator import bootstrap) were already fixed pre-merge
(commit `8b84886`) and are not re-counted here.

## Classification summary
- **Blockers for P10:** none (AC-24 pilot is the P10 activity itself, not a blocker).
- **Blockers for public launch:** EX-12 deployment, live email, human translation review, legal
  review, K1/K2 data review (all external-access / review gated, not code defects).
- **Non-blocking Capstone limitations:** distributed limiter, checkpoint residual, CSRF posture,
  localization debt, environment flake, browser matrix, partial diagnostics/profile surfaces.
- **Optional validations:** all live-provider runs (realtime, OIDC, Adzuna, RAGAS, OCR, speech,
  multilingual, multi-agent).

**P0 defects: 0 · P1 defects: 0** → P9 is not blocked by any defect.
