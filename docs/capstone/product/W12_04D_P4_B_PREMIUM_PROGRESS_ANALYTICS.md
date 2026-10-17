# W12.4D-P4-B Premium progress analytics and interview comparisons

Status: **CODE QUALIFIED. PREMIUM PROGRESS ANALYTICS IMPLEMENTED. INTERVIEW COMPARISONS IMPLEMENTED. CANDIDATE ROLLOUT DISABLED. COMMERCIAL PREMIUM NOT ACTIVATED.**

Starting point: main `808c4a0108cb2991a7520ffa8df8a50ee39c26d7` (P4-A merged as PR #173). No migration: Alembic head stays `0033_usage_quotas`. No LLM call, no stored snapshot, no cache.

## 1. Data inventory
| Datum | Source | Reliability |
|---|---|---|
| Interview id, user, created and ended time, status, mode | `interviews` | present and reliable (`created_at` is the server timestamp used for ordering) |
| Opportunity link | `interviews.opportunity_id` (nullable FK, SET NULL) | reliable where set; NULL for standalone and legacy rows; never inferred |
| Role, career level, industry | `interviews.configuration` JSON | present for normal sessions; legacy rows may lack them |
| Interview type, difficulty | per question (`questions.question_type`, `difficulty`) | present; an interview has a MIX of types, there is no single interview type |
| Per-answer overall score (0 to 100) and seven rubric ratings (1 to 10: relevance, structure, evidence, role knowledge, problem solving, communication, credibility) | `answers.evaluation` JSON (model-generated) | present when the answer was evaluated; may be missing or malformed |
| Report overall readiness score (0 to 100) | `reports.report` JSON | present when a report was generated; optional |
| Answer timing | `answers.timing_metrics` JSON | partial; not used by analytics |
| Scoring model and version | NOT stored with an interview | missing: always reported as a limitation |
| Seniority/difficulty as a comparable attribute across attempts | career level (configuration) only | partial |
STAR is not a scored dimension and no STAR score exists anywhere in the analytics.

## 2. Architecture
`src/application/progress_analytics.py` (pure, deterministic functions plus `PremiumAnalyticsPolicy`), `InterviewRepository.analytics_rows` (light read-only rows), `src/api/routes/progress_analytics.py`, `src/api/schemas/progress_analytics.py`. Analytics are computed on request from retained records; nothing is stored, so deletion, account closure and plan changes apply on the next request and a Premium result is never served after a downgrade.

## 3. Implemented metrics (descriptive only)
Per interview: practice score (plain mean of its evaluated answers' overall scores), scored-answer count, low-sample flag, report score as recorded. Across interviews: chronological points, first, latest, average and best score, change between the first and latest scored interview with a direction (improved, declined, unchanged), score distribution bands (0-39, 40-59, 60-79, 80-100), per-question-type averages, practice frequency (last 30 and 90 days, by month), seven-dimension rubric averages with strongest and weakest only when there is a measurable difference and a minimum sample, and recurring model-generated improvement areas (top five, labelled as model-generated). No readiness probability, prediction or hiring signal exists.

## 4. Methodology
Scales: overall 0 to 100, rubric 1 to 10, never mixed. Aggregation: unweighted arithmetic mean, rounded to one decimal; there are no weights. Minimum sample: a trend needs two scored interviews; fewer than three scored answers in an interview raises `low_sample` (shown, never hidden or weighted); strongest and weakest need at least two measured dimensions, one with three answers, and a difference after rounding. Missing values are excluded, never converted to zero; out-of-range, non-numeric, boolean and NaN values are treated as corrupt and ignored. Ordering: `created_at` then `id` (ties are deterministic). Comparable context for a trend: same role and level (case-insensitive) for the first and latest points, otherwise a warning is shown. Outliers are not removed. No statistical significance, confidence interval or causal claim is made. The scoring version is not recorded, so scores from different model or rubric versions may not be strictly comparable.

## 5. Comparison
`GET /progress/analytics/compare?base=&target=` compares two eligible completed interviews: score difference and direction, per-dimension differences only where measured on BOTH sides, comparability reasons (different role, level, opportunity, question-type mix, question count, low sample) and standing limitations (`scoring_version_not_recorded`, `model_feedback_not_objective`, `difference_is_not_proof_of_skill_change`). A difference is a difference in recorded practice scores, not proof of a change in skill.

## 6. Opportunity-scoped analysis
Supported through the stored `opportunity_id` only (`?opportunity_id=`), with an ownership check (foreign and missing are the same 404). Interviews are never linked by text similarity; unlinked interviews are simply not part of an opportunity view. No new Opportunity data model was added; Preparation Packs remain P5-A.

## 7. Entitlement and rollout
`PREMIUM_ANALYTICS_ENABLED = False` (code constant). While False every route answers `feature_disabled` with no data, including for a genuine Premium account, and the disabled route does not probe ids. With the gate on, access needs an ACTIVE Premium-plan subscription through `plan_state.resolve_plan_state` over `EntitlementService`; Basic, `premium_preview`, forged headers, query parameters, localStorage, expired, unknown and unreadable state are `not_entitled`. The decision is enforced on the server independently of frontend visibility, and a synthetic override is refused outside development and test.

## 8. History authorization
The analysed set is exactly the caller's eligible COMPLETED history under `HistoryAccessPolicy.window_for` through `InterviewRepository._eligible_ids` (no second rule). The analytics entitlement can never widen history: tested with analytics enabled for a still-restricted window, where only the window is aggregated and a comparison involving an owned interview outside it is 403 `history_not_available`. Foreign ids are 404. Workspace membership grants nothing: a workspace member sees only their own interviews.

## 9. API contracts
`GET /progress/analytics` returns `state` (`feature_disabled`, `not_entitled`, `no_data`, `insufficient_data`, `ready`), counts, points, summary, distribution, rubric, by_question_type, frequency, improvement_areas, filters, methodology and limitations. `GET /progress/analytics/compare` returns `state` (`feature_disabled`, `not_entitled`, `insufficient_data`, `ready`) and the comparison. Only measurements are returned: no transcript, answer text, question text or feedback prose (tested with sentinel strings). Unsupported comparison inputs (same interview twice, bad ids) are 422.

## 10. Frontend
`components/progress/PremiumAnalytics.tsx` is rendered by the existing Progress page. It renders only server measurements; on `feature_disabled`, `not_entitled`, a failed request or a malformed payload it renders the existing P3 planned notice (no chart, no number, no link, no CTA). Ready state: SVG trend chart with `role="img"` and a computed label plus a data table as the text alternative, summary figures, change with a non-colour marker, rubric list with bars and numbers, question-type, distribution and frequency cards, model-generated improvement areas, truncation notice, opportunity filter (only when links exist) and a two-interview comparison with labelled selects. No sample or fabricated data exists.

## 11. Downgrade and re-upgrade
Under isolated synthetic enforcement: Premium to Basic returns `not_entitled` with no data and the comparison endpoint is not a history bypass; the 3-interview Basic history is unchanged and no record is touched. Re-upgrade restores the identical full result with no duplication, regeneration or cache. No real downgrade behaviour is activated.

## 12. Privacy
Read-only, caller-scoped, no snapshot or derived store, no retention extension, no transcript duplication. Deletion and account closure continue to work (a deleted interview disappears from analytics immediately; tested). Data export and deletion rights are unrelated to this gate. No live candidate data is used in tests.

## 13. Localization
Fragment `w12p4b` (`analyticsUx`, 65 keys x 8 locales; no ninth locale); dates and numbers use the locale formatters. Interview-type ids are shown humanized from the stored id (they are not translated yet; a known limitation).

## 14. Responsive QA and accessibility
`e2e/premium-analytics-p4b.spec.ts`: ready state across {1280, 768, 390} x {light, dark} x {en, de, ru} plus disabled and not-entitled states, all passing (no horizontal overflow, no raw keys, no unnamed controls, all selects labelled, h1 present, chart has role and label, text table present, comparison result shown, no links or checkout). Programmatic checks only; no WCAG certification is claimed. Chart tooltips are native SVG titles; the table is the keyboard- and screen-reader-accessible alternative.

## 15. Performance
Four bounded queries regardless of history size (tested). Histories of 0, 1, 3, 10 and 100 interviews and a 1,000-interview history (capped to the newest 500 with `truncated: true`) complete in seconds on SQLite. Only measurement columns are read; the evaluation JSON is loaded but never returned. No caching was introduced. Index use rests on the existing `user_id` and `opportunity_id` indexes; no query plan was captured on PostgreSQL.

## 16. Tests
Backend `tests/test_progress_analytics_p4b.py` (39): correctness fixtures (empty, single, two, three, flat, negative, missing, corrupt, ties, rubric, strongest and weakest thresholds, types, distribution, frequency, improvement areas, low sample, comparison, different contexts), security (disabled, Basic, forged plan, preview, expired and unknown and unreadable, production refusal, cross-user and workspace, history-window non-widening, downgrade, re-upgrade, deleted, bad ids, opportunity isolation, Basic progress unchanged, read-only and import-free of providers and billing), scale, gates off, head unchanged. Frontend 12 unit tests plus the eight-locale check; Playwright 20 new tests.

## 17. Known limitations
No scoring version is stored, so cross-version comparisons carry a standing caveat. Per-answer evaluations are model-generated and subjective. Interview-type labels are not translated. The 500-interview cap is a pragmatic bound, not a product decision. PostgreSQL query plans were not captured. No allowance, price or reset period is approved and nothing is enabled.

## 18. Product acceptance requirements (before enabling)
Owner approval of metric definitions and wording, review of the model-generated caveats by legal and product, a PostgreSQL performance check on a realistic history, approval to flip `PREMIUM_ANALYTICS_ENABLED`, and the separately approved history rollout, entitlement activation and pricing.

## 19. P5-A readiness
Ready on instruction. Not started here.

## 20. Programme dependencies (unchanged)
P4-A quota enforcement disabled; numerical allowances unapproved; PostgreSQL quota concurrency and reservation-expiry validation pending; Practice per-session cost exposure pending; live Redis validation pending; Fast model quality and cost evaluation pending; Basic-to-Fast not approved; history and model-profile rollouts disabled; Premium pricing unapproved; Ask4Mo UG incorporation pending; dedicated Stripe onboarding pending; Brevo live validation pending; research-cache evaluator isolation unresolved; four pre-existing evaluators failing and unresolved pending independent triage (`eval_company_intelligence`, `eval_marketing_product_trust`, `eval_opportunity_journey`, `eval_release_candidate`); product coverage `insufficient_evidence` 94% (n=412) BELOW GATE; RC-P10-004 not created.
