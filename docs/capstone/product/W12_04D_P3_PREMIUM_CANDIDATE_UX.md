# W12.4D-P3 Basic/Premium candidate experience

Status: **CODE QUALIFIED. BASIC/PREMIUM CANDIDATE EXPERIENCE PREPARED. COMMERCIAL PREMIUM NOT ACTIVATED.** No rollout or billing gate was changed, no migration was added, no Stripe or live provider call was made.

## 1. Starting SHA
Branch `feat/w12-04d-p3-premium-candidate-ux` from main `61368533bc3e0b60a75868cf0e76145e2710a2cb` (P2-A, P2-B and P2-C verified merged). Alembic head unchanged: `0032_ai_operation_events`.

## 2. Existing UX assessment
Before P3 the pricing page offered Premium through a request path that read as a purchase, the Account page showed only a subscription panel, History and Progress had no way to explain a server-side restriction, the session-continuation error for a profile no longer authorised was a generic message, and nothing described what Basic and Premium actually include. Homepage and footer copy implied a purchasable Premium.

## 3. Components added or modified
Added: `components/plan/{StatusChip,PlanOverview,ModelProfilePanel,HistoryAccessNotice,SessionTransitionNotice}.tsx`, `lib/plan/capabilities.ts`, `lib/i18n/messages/w12p3/*` (82 keys x 8 locales). Modified: `AccountPanel`, `HistoryClient`, `HistoryDetailClient`, `PracticeProgress`, `PracticeClient`, `useInterview` (flag `needsNewSession`), `PricingContent`, `lib/pricing.ts`, `lib/api/{types,client}.ts`. Backend (display metadata only): `HistoryAccessOut` and `ProgressAccessOut`, `InterviewRepository.count_completed`, owner-window rule on shared reads.

## 4. Plan-aware architecture
The server is the only authority. The client renders `access` metadata returned by `GET /history/interviews` and `GET /progress` and the catalogue from `GET /model-profiles`. It never computes, stores or sends a plan, and localStorage or any client value changes nothing. The capability matrix (`lib/plan/capabilities.ts`) states, per cell, one of five truthful statuses: available now, available under an active entitlement, planned but not implemented, commercial activation pending, operationally unavailable. `premium_preview` is never treated as Premium.

## 5. Account experience
Account shows the plan overview (no purchase flow, no pricing, no cancellation control, no paid-subscription claim) and the model-profile panel (read-only, no controls).

## 6. History UX
Gate disabled: unchanged. Gate enabled and the caller restricted: the server returns `restricted`, `window` and `hidden_count`; a notice states that older interviews are retained, not deleted, with a link to Account only (no upgrade button, no urgency copy). An owned but restricted detail page shows a calm card using `states.historyRestricted` plus a retained-not-deleted line and a back button.

## 7. Progress UX
A scope notice appears only when the server marks the view restricted. Trends and comparison are shown as a planned section with a planned chip (no fake analytics). Trends and comparison are P4.

## 8. Model-profile UX
Selector inactive (the current state): no selector, no controls, informational list only. Under synthetic enforcement tests: Basic sees Fast authorised, Premium sees all three. Unknown ids are ignored, no raw model id, no cost or quality claim is shown.

## 9. Feature-discovery states
Thirteen capabilities, each with its own Basic and Premium cell status (see `lib/plan/capabilities.ts`). Premium Practice and research cells read "commercial activation pending"; trends, comparison, Preparation Packs and voice read "planned".

## 10. Locked and unavailable states
Locked states are explanatory text only (status chips), never buttons, never a checkout link. Provider-down uses the existing localized error cards.

## 11. Downgrade messaging
Records are preserved; saved independent artifacts remain readable; reports and feedback follow the history policy; new Premium generation is restricted by the server. Copy never uses loss framing.

## 12. Saved artifacts
No Preparation Packs exist (P5-A). Story Bank items are independent and unaffected by the history window.

## 13. Shared-link policy status
**Bounded correction implemented.** `_report_load` in the sharing service now applies the OWNER's current history window to a shared interview report: outside the window the read is refused like a missing resource; the grant is not deleted or altered, so it works again when the owner's entitlement returns; revocation still works; behaviour is unchanged while `HISTORY_RESTRICTIONS_ENFORCED` is False. This supersedes the P2-B statement that existing shares are unchanged (P2-B section 12). Tests: `tests/test_p3_candidate_ux_backend.py`. History activation still needs separate owner approval.

## 14. Pricing corrections
Premium is shown as not available yet. The EUR 19.99 figure appears only as an unapproved preview, with no purchase link, no checkout and no billing wording. Premium `ctaKind` is `unavailable`. Page metadata corrected.

## 15. Homepage and footer corrections
Claims that implied a purchasable Premium were replaced (`marketing.homePricingBody`, `ctaBody`, `footerNoBilling`). No guarantee, recruitment or human-coaching claim is made.

## 16. Eight-locale results
en, de, fr, es, it, pt, nl and ru, 82 new keys each; key-resolution tests, raw-key and em-dash scanners, Russian English-leakage test (Fast, Balanced, Advanced added to the brand-token allowance) all pass. No ninth locale. The slogan invariant is untouched.

## 17. Responsive QA
`e2e/plan-ux-p3.spec.ts`: 18 configurations ({en, de, ru} x {1280, 768, 390} x {light, dark}) over `/pricing`, `/account`, `/history`, `/history/12`, `/progress`. Checks: no horizontal overflow, no raw keys, no crash, an h1 where applicable, named controls, no checkout link, no controls in the model-profile panel. All pass. The Practice transition notice is verified at component and controller level (heavy Practice mock not used); this is a recorded limitation.

## 18. Accessibility findings
Notices use `role="region"` or labelled headings, status is conveyed by text and chip rather than colour alone, and no unnamed links or buttons were found. Programmatic checks only; no WCAG certification is claimed. A first-run false positive (closed `<details>` benchmark links read as unnamed by `innerText`) was a test-method issue, corrected to `textContent`.

## 19. Security testing
Backend (6 tests): access metadata with gate off and on, forged plan header ignored, share restricted-and-restored lifecycle, gates remain off. Existing P2-B and P2-C suites cover cross-account (404), owned-restricted (403 `history_not_available`), direct API bypass, unknown profile ids, unverified preview. Frontend (39 tests): modified localStorage, unknown ids, inactive selector, restricted detail, refused continuation without reload.

## 20. Remaining gaps
Not activated: P2-A enforcement (live Redis validation pending), P2-B history rollout, P2-C model enforcement. Fast quality evaluation pending. Premium numerical allowances and pricing not approved. Ask4Mo UG incorporation, dedicated Stripe account and Stripe sandbox validation pending; Brevo live verification deferred; research-cache evaluator isolation unresolved. Product coverage: `insufficient_evidence` 94% (n=412) is BELOW GATE; RC-P10-004 not created. The production-transition notice and the grandfathering decision for existing Basic sessions are **pending owner approval**; `MODEL_PROFILE_ENFORCED` remains False and Basic is not moved to Fast.

## 21. P4 dependencies
Progress trends and comparison, Premium numerical allowances and plan-family limit entitlements replace the placeholders presented here as planned.

## 22. Release implications
Merging P3 changes presentation and a bounded shared-read rule that is inert while the history gate is off. No candidate loses access, no Basic account changes model, no purchase path exists. Enabling any gate remains a separate owner-approved release.

## Qualification record
Frontend vitest 104 files / 1016 tests, typecheck, lint and build clean; Playwright 363/363 (two stale assertions updated deliberately: homepage Premium sentence, and a billing test scoped to its panel because the Account page now also has a model-profile retry); backend pytest 4007 passed, 4 skipped, 0 failed; ruff and `git diff --check` clean. CI-safe evaluators exit 0 except four that fail identically on main before P3 (`eval_company_intelligence`, `eval_marketing_product_trust`, `eval_opportunity_journey`, `eval_release_candidate`); these are reported, not altered. `eval_release_matrix` PASS (99 rows, 88 pass, 11 partial, 0 other); `eval_product_coverage` insufficient_evidence BELOW GATE.
