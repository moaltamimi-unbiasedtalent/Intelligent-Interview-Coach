# Task 07 — History browser readiness and image qualification

## Verified baseline — 27 October 2026

Main `90391b8ca654853af11c8d8c3bd1260f24970319` includes merged PR #274
(CSP) and #275 (PostgreSQL checkpoint recovery). All seven post-merge main workflows
passed: [CI](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749659),
[images/CSP](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749662),
[migration](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749705),
[Redis](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749675),
[budget](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749677),
[recovery](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749689),
[admission](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40457749709).
PR #273 remains open and unmerged at `bc75b4c772e5468934d033fe565eac5b921e4927`.
Its implementation and historical failed campaign evidence are untouched.

## Diagnosis and confidence

The actual [failed Browser run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40361429555)
and retained `playwright-traces` artifact were inspected. At the 60-second test
cutoff, the trace had one unfinished local image request:
`/_next/image?url=%2Fimages%2Fask4mo%2Fask4mo-empty-history-ink.png&w=384&q=75`.
It had no observed response/completion for approximately **56,405 ms**. The snapshot
already displayed the History heading, empty-state heading and both action links.
The trace also recorded four TypeErrors on earlier Opportunities/Practice pages.
The workflow log has no optimizer/server error establishing why that request did
not complete. A trace cut off at a deadline is not proof of an infinite retry.

The **unchanged** candidate test passed ten production-build repetitions locally,
zero retries/skips. All ten real History optimizer requests completed HTTP 200
(3.285–297.570 ms; eight HIT, one STALE, one MISS). However those passing tests
recorded **100 console errors**: the wildcard mock returned `{}` where pages
expected structured list/options/plan/sharing responses. Global network idleness
had allowed broken pages to count as ready. This is a reproduced test-harness
readiness/fixture defect, not evidence of a malformed live backend response.

**Classification:** reproduced and repaired test-harness false-readiness and invalid
fixtures; **historical optimizer stall NOT REPRODUCED**, underlying cause
**INCONCLUSIVE**. Confidence is high in the fixture/readiness findings and low in
any proposed optimizer-stall explanation. No claim that it was a harmless flake,
startup contention, corrupted image, caching defect or CSP regression is supported.
The historical stall's cause remains unresolved; this PR does not claim to repair
Next.js image optimization. It delivers the supported harness repair and guards
that expose an image failure distinctly. A recurrent stall must still fail.

The source PNG is byte-identical to PR #273's image (Git blob comparison), has a
valid PNG signature/dimensions, and is actually decoded by Next.js and Chromium.
No image asset, production component, caching configuration, middleware or CSP
policy is changed. [Measured local evidence](evidence/HISTORY_BROWSER_LOCAL.json)
keeps the original failure separate from passing repetitions and their limits.

## Focused change

The candidate sweep navigates with DOMContentLoaded, verifies the main heading and
completion of the actual skeleton loaders, and opens/closes the real controlled
More menu to prove hydration/navigation. History additionally requires its precise
empty-state heading, Start Practice and Learn about History links. Pricing verifies
its rendered navigation. API fixtures now provide valid empty read contracts while
all existing gate settings, role permissions and forbidden-endpoint patterns remain
unchanged.

A **500 ms security observation window follows deterministic readiness on every
route**. This preserves the old networkidle minimum observation interval; it is
not the readiness signal. Existing external-origin and gated-endpoint assertions
run after every route and at the end. An explicit delayed-request control issues a
synthetic gated request after readiness, inside the API mock only, and requires the
security assertion to reject it. It sends no request to a backend/provider.

History's actual lazy image is scrolled into view, must finish and decode with
positive natural dimensions, and must have a successful optimizer response and no
outstanding optimizer request. A pending optimizer fails explicitly as
`history_image_optimizer_pending` within the existing 10-second assertion bound;
a failed HTTP response or decode has its own failure label. Global 60-second test
and 10-second expectation limits, retries and workers are unchanged.

Independent DPR 1/2 cases qualify real image requests and enforced nonce CSP in a
production build. Positive cases require one optimizer response, HTTP 200, loaded
pixels, no pending image requests, no unexpected external/gated calls, and no
console/page/unexpected transport errors. The failure case points the DOM image at
a real missing local asset through the real optimizer: HTTP 400 must be reported
as `history_image_http_400`, once without retries, while the History controls and
actual navigation to Practice continue to work. The expected resource-error console
entry is explicitly asserted; it is not suppressed. No image request is mocked,
blocked, removed or intercepted.

Sanitized diagnostics retain request/response/finish/failure timing, host/path,
resource type, optimizer status/cache/source, outstanding requests, document state,
menu hydration, console/page error categories, Node/browser versions, source SHA
and dirty-tree flag. No headers, cookies, bodies, raw console text or arbitrary
query strings are stored. Every failed request is recorded. Only ERR_ABORTED on
identified Next.js prefetches is classified as an expected navigation cancellation;
other failures, including image aborts, fail qualification.

## Qualification and limits

Local repeated qualification: **50 passed, zero failed/skipped/retries**:
ten full candidate sweeps, twenty positive image cases, ten actual missing-image
cases and ten delayed gated-detector controls. Positive cases had zero console,
page or unexpected transport errors and zero outstanding image requests. Local
cache observations were 26 HIT / four STALE; the separate original baseline run
included a real MISS. The stricter prefetch classification and actual post-failure
Practice navigation then passed both affected cases. Frontend unit suite:
**1,547 passed**; lint and focused browser TypeScript checks passed. Production
builds were executed by the CI-mode Playwright-owned server on isolated port 3137;
no unrelated server was reused. Local Node **24.15.0** / Chromium **153.0.8010.12**
is reported as local evidence, not an assertion that macOS equals the Linux runner.

The Browser workflow explicitly checks out the reviewed head, type-checks these
browser tests, repeats all five cases ten times on Linux/Node 20 with zero retries,
retains only sanitized JSON evidence for successful repetitions, then executes the
**complete unchanged primary suite plus the new cases**. This is required, not
optional or failure-suppressed. Other full CI and immutable-image/CSP checks remain
mandatory. Exact final source SHA, workflow links, image/cache observations and
full Browser totals are recorded in the focused PR's final evidence addendum.
Current local files are labelled uncommitted working-copy observations.

Ten repetitions are bounded empirical evidence, not a statistical reliability
claim. They cannot establish that an unreproduced historical optimizer stall will
never recur. The explicit image checks prevent semantic readiness from concealing
such a recurrence. The complete PR #273 connected campaign remains NOT RUN here.

## CI diagnostic follow-up (not final qualification)

The first Linux repetition run at `e9f1f980` recorded **46 passed / four failed**.
All candidate sweeps, positive images and delayed-detector controls passed. Four
missing-image cases failed the new strict transport assertion after the real
Practice link was clicked: `/practice` returned HTTP 200, then a fetch body was
cancelled, while the destination rendered and its menu worked. This is distinct
from the historical pending image request. All ten expected missing-image responses
were HTTP 400; successful image cache outcomes included two MISS, 44 HIT and four
STALE. The full primary suite was NOT RUN after that prerequisite failure.
The failed workflow/artifact is retained:
[CI diagnostic run](https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/actions/runs/40461671496).
Additional request IDs, derived RSC/prefetch flags, content type/status and safe
transport codes are being qualified to identify the cancellation precisely; no
broad abort exemption or production change is justified by the first record.
Local diagnostic CPU throttling did not reproduce the Linux cancellation. Final
qualification must be recorded separately; the 46/4 result is not rewritten PASS.

## Preservation and release position

Pre-task inventory: **47 existing worktrees, 315 original branch tips and 49
protected-file hashes**. The focused worktree/branch is additional. Original
checkout/artwork, unpublished work, secrets/env files, private stores and the original
SQLite database (last observed 0027) are not opened for testing or modified. No
worktree/branch removal, force push or Docker prune occurs. Preservation audit after implementation found zero changes to all 47 original
worktree statuses, 315 branch tips and 49 protected-file hashes. PR #273's branch and failed 27/2/6 evidence remain historical.

**R1.0 remains 40/45 integrated.** 00A/00B/07B/07C/08A stay open/incomplete. Task 07
remains OPEN until full connected qualification; Task 08 remains blocked. Engineering
PR qualification is separate from hosted staging, human review and release gates.
PG-01–PG-15 and LG-01–LG-14 retain existing approval states (only historical PG-11
PASS; zero hosted-qualified languages). No owner approval or language activation
is added. No deployment, paid AI/embedding, live email, real database migration,
external registry publication or automatic merge is authorized/performed.

Stop after this focused PR. **Only after review, merge and green post-merge main**:
safely reconcile PR #273 with reviewed main without losing its original history;
rebuild immutable application/operator images and manifests at the reconciled SHA;
rerun the complete mandatory disposable campaign, including PostgreSQL recovery
without API restart and real Caddy sign-in/CSP. Preserve failed history and append
fresh source-bound results. Missing authorized hosted/live checks remain NOT RUN.
Do not mark the original campaign PASS or start Task 08 from this browser PR.
