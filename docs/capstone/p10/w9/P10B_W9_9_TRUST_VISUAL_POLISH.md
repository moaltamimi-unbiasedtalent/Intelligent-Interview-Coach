# P10B-W9.9 - Trust & Visual Product Polish

Frontend-only wave. **No backend, schema or migration change** (Alembic head `0014_opportunities`), 0 paid/live
calls, no RC-P10-003, Pilot 2 not resumed, W9.10 and W10 not started.

## 1. Baseline
`main` = `d0504a8eabfe9d40eba5c0553533c31f7c82cb7d` (W9.8 merged, PR #103). Branch `feat/p10b-w9-9-trust-visual-polish`.

## 2. Audit methodology
A throwaway Playwright harness (not committed) with a deterministic network mock captured full-page screenshots of
`/app`, Opportunities, Prepare, Practice, Progress, History, Settings, Account, `/account/data`, Help, Trust, Privacy,
AI transparency, Documents and Sources in desktop (1280) and mobile (390), light and dark, populated and empty; changed
surfaces were re-captured in German and Russian. Source review covered nav, States, Alert/Card/Button, AgentSources,
AgentConversation, AccountMenu and the legal/trust catalogues. W9.8 `/account/data` was used as the quality reference
without copying its layout.

## 3. Findings matrix (P1 = 1, P2 = 6, P3 = 5)
| # | Surface | Issue | Type | Sev | Scope | Resolution |
|---|---|---|---|---|---|---|
| 1 | Account, legal retention copy (8 locales) | Said deletion removes "agent context / agent checkpoints" - contradicts PRIV-W9-01 | trust clarity | **P1** | shared copy | Fixed: claim removed everywhere; Account copy now states some preparation-chat working data may remain |
| 2 | Trust page | 17 identical stacked cards, no grouping, no AI-limitation statement, no data link | hierarchy / AI transparency | P2 | local | Fixed: 4 labelled groups, "AI can be wrong", link to Data & privacy |
| 3 | Mo conversation | No in-context cue that Mo is AI / sources scope | AI transparency | P2 | local | Fixed: one calm note under the conversation with link to AI transparency |
| 4 | Sources list | Unnumbered, so `[n]` markers in the answer could not be matched | evidence/provenance | P2 | local | Fixed: ordered `[n]` list + hint |
| 5 | Navigation | Data & privacy and Trust reachable only via Account page / marketing | navigation | P2 | shared | Fixed: account menu entries |
| 6 | Settings | First card titled "Mo coaching style" but holds name/role/geography; data link text did not match its target | terminology | P2 | local | Fixed: "Profile and coaching style"; link text names Data & privacy |
| 7 | Home | "Ask Mo" button wrapped to two lines; composer narrower than neighbouring cards | spacing / CTA | P2 | local | Fixed |
| 8 | History | Row title repeated in metadata line | consistency | P3 | local | Fixed |
| 9 | Home | Welcome-back card sits above the brand/hero; brand lockup duplicates header | hierarchy | P3 | local | Deferred |
| 10 | Practice / Account | No shared PageHeader (title lives in card / h1) | consistency | P3 | local | Deferred |
| 11 | History | "{n} question(s)" non-plural phrasing in all locales | terminology | P3 | shared copy | Deferred (needs plural keys x8) |
| 12 | Help | Single 13k px mobile page | navigation | P3 | local | Deferred |
| 13 | Home mobile | Placeholder truncated | responsive | P3 | local | Deferred |

Empty states (Opportunities, Progress, History, Memory) already answer what/why/next and were left unchanged. Error states
keep the W9.7A section/page/fatal hierarchy; copy audit found no misleading connection blame (offline text only for a real
offline signal). Dark theme: no contrast defects found in scoped surfaces.

## 4. Trust Claim Matrix
| Claim (surface) | Evidence in code/docs | Wording | Action |
|---|---|---|---|
| Mo is AI and can be wrong (cue, Trust, AI transparency) | AI transparency "Limitations" | "Mo is AI and can make mistakes" | added cue + Trust item |
| Sources shown when an answer uses career evidence | AgentSources renders `run.sources` only when present | "Sources are listed when an answer uses career evidence" | added |
| Insufficient evidence -> explicit limitation | W9.7A localized insufficient-evidence note | existing copy | unchanged |
| Practice feedback is not a hiring decision | `practice.evalDisclaimer` | existing | unchanged |
| You approve saved memory / remove memories | HITL APPROVE_MEMORY, memory DELETE, W9.8 | existing | unchanged |
| Sharing is explicit, view-only, revocable | share grants, W9.8 revoke copy ("cannot be taken back") | existing | unchanged |
| Export / delete | W9.8 export + account deletion | Trust "Export and delete" | unchanged; agent-context claim **removed** |
| Preparation chats fully deleted | **Not true** (PRIV-W9-01) | - | never claimed; limitation stated |
| Consent/legal acceptance history | **Not stored** (PRIV-W9-02) | - | never claimed |
| Absolutes (100% secure, GDPR compliant, bias-free, human reviewed, enterprise-grade) | no evidence | - | none introduced; asserted by test |

## 5-11. Changes
Surfaces: Trust, Mo conversation (Prepare), Settings, Account menu, Home, History. Shared components: `AgentSources`,
`AccountMenu`; copy fragments. New fragment `lib/i18n/messages/w99` (`trustUx`, 15 keys x 8 locales). Corrected
`account.privacyDataDesc` and `legal.retentionExport` in every locale. Typography/spacing/cards/error and empty-state
primitives were audited and intentionally left unchanged (no inconsistency severe enough to justify churn; W9.9 is not a
redesign). Mobile nav unchanged (works at 390). No new dependency, font, icon library or animation.

## 12-16. QA
Responsive/accessibility: programmatic no-horizontal-overflow assertions at 390px in light and dark for de and ru on
`/app`, Settings, History, Trust, Account, Data & privacy; semantic h2 per Trust group; ordered list semantics for
sources; menu items keyboard-focusable with the existing roving behaviour; ConfirmDialog unchanged. Visual review of
German and Russian (desktop light, mobile dark): no wrapping/overflow defects. Localization: scanner 0 offenders;
all `trustUx` keys present, dash-free and slogan exact in 8 locales. **All non-English copy, including Russian and the
corrected legal/privacy strings, remains an engineering translation pending human/legal review.**

## 17. Performance
Shared first-load JS unchanged (103 kB). Route first-load deltas are about +3 kB from the extra catalogue strings
(for example `/trust` 385 -> 388 kB). No new client-heavy component; all edits were to existing client components.
TD-W9-03 (locale-aware font/bundle work) untouched.

## 18. Tests
Vitest `tests/trust-polish.test.tsx` (7): grouped Trust page, no absolute claims, numbered sources, AI cue gating, account
menu links, truthful deletion copy x8, `trustUx` completeness. Playwright `e2e/trust-polish.spec.ts` (4): journey reachability
including Data & privacy and Trust via the menu, Home button single line, de/ru overflow light/dark. Totals: frontend 507
passed, Playwright 199 passed, 22 CI evaluators green, ruff clean, typecheck/lint/build green. Backend untouched (pytest
unchanged; 13 known `.env`-dependent failures pre-exist on `main`).

## 19-21. Status
Backend/schema: unchanged, no migration. **Open and not closed here:** PRIV-W9-01 (preparation-chat indexing/deletion),
PRIV-W9-02 (consent/legal-version persistence), TD-W9-01 (Tailwind `token/NN` opacity; no new invalid classes added),
TD-W9-02 (full test-isolation audit), native Russian review, legal-copy review, live generated-language validation,
metadata localization, locale/bundle optimisation. Deferred polish: findings 9-13.

## 22. W9.10 handoff
Product Positioning / Comparison Foundation: use the Trust Claim Matrix as the rule for what may be said; positioning text
must stay factual, avoid superiority claims, and keep PRIV-W9-01/02 limitations visible. External competitor research needs
separate authorisation.

## 23. Confirmation
0 paid/live calls. No migration. No RC. Pilot 2 not resumed.
