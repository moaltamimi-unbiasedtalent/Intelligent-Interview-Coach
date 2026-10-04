# P10B-W10.5 - Billing & Payment Administration (MOCK BILLING ONLY)

**Status:** COMPLETE. Merged in PR #123 (`8e33805`) with green CI. W10.7 (AI and model administration) follows.
One additive migration (`0021_billing_admin`). No new dependency. 0 paid/live calls.

**MOCK BILLING - NOT LIVE BILLING.** There is no live payment provider, no checkout, no payment-method collection, no card data, no tax engine, no real money movement. Every Admin API, screen and document says so.

**The invariant: billing state is not entitlement state.** Failed payments, past-due invoices, refunds, provider-side cancellation, billing events and price changes never change the W10.4 product subscription, the compatibility tier or any entitlement. No policy connecting them exists.

## 1. Starting point
`main` `54ee591ec1f038d00d4c4699993dd3b526a02ba1` (W10.10 merged, PR #122), clean tree, Alembic head `0020_privacy_legal_admin`. W10.10 is marked COMPLETE in this branch's docs.

## 2. Branch
`feat/p10b-w10-5-billing-payment-admin`.

## 3. Billing absence audit (from code)
| Capability | State before W10.5 | W10.5 action |
|---|---|---|
| price, currency, interval, trial, visibility | none (W10.4 deferred them) | versioned commercial terms (metadata) |
| checkout, payment method, billing portal, tax | none | none (not built) |
| invoices, payments, refunds | none | mirrored MOCK metadata |
| billing customer / provider subscription | none | mirrored MOCK references |
| webhook / events | none | normalised internal events and a job, no public endpoint |
| coupons, discounts | none | deliberately not built |
| Premium | preview, not purchasable | unchanged |

## 4. W10.4 handoff
Terms attach to the stable `plan_versions.id`. Entitlements, plan names and capability definitions are not duplicated. A plan version with no terms is unconfigured, which is not free and not zero.

## 5. Four-layer separation
Authorization (`require_permission`), technical capability (`/capabilities`), entitlement (W10.4 `EntitlementService`) and billing (this wave) stay separate. Billing code does not import or write subscriptions, plan entitlements or the tier (evaluated statically and tested through a 13-step before/after comparison).

## 6. BillingProvider interface
`BillingProvider` (Protocol): `name`, `live`, `capabilities()` and `refund(idempotency_key, provider_payment_id, amount_minor, currency)`. Nothing speculative: no checkout, tokenisation, tax or portal.

## 7. MockBillingAdapter
Deterministic, offline and labelled. No network, money, card, bank, tax or external invoice. The same idempotency key always returns the same `mock_re_...` refund id; `calls` records every call; a fixture hook injects retryable or rejected failures; static helpers build normalised events with deterministic ids.

## 8. Production guard
`BILLING_PROVIDER` defaults to disabled. `mock` is accepted only when `API_ENV` is development, dev, test, testing or local (the same set as the dev conveniences; pinned equal by a test). Mock in production, staging or any other environment raises `BillingConfigurationError`; the API reports billing disabled with the reason (never "live"); any provider value other than disabled or mock is rejected because no live provider exists.

## 9. Commercial-term model
`billing_commercial_terms`: plan version, version number, `amount_minor`, `currency`, `billing_interval`, `trial_days`, `visibility`, state (active, retired), approval reference, timestamps. One active version per plan version (partial unique index); unique version number per plan version.

## 10. No invented price
Zero prices, customers, invoices, payments or refunds are seeded (migration is schema only; verified). Test fixtures create deterministic mock data only inside temporary databases.

## 11. Amount model
Integer minor units, 0 to 100,000,000. Floats, booleans, strings and negatives are rejected (strict API integers plus service and database checks).

## 12. Currency
A structurally validated uppercase three-letter code for MOCK metadata. It does not mean a live provider supports it; there is no FX or conversion.

## 13. Interval
`month` or `year`. No scheduler: there is no recurring real charge.

## 14. Trial metadata
Optional `trial_days` (1 to 365). It is metadata only: it grants no product trial and no policy links it to subscriptions. No default is seeded.

## 15. Visibility semantics
`public`, `private`, `internal`. Catalogue metadata only: `public` does not mean purchasable.

## 16. Premium preview boundary
Premium stays a preview with nothing to buy. No Buy, Upgrade, Subscribe, Checkout, payment-method or billing-portal affordance exists on any candidate surface (scanned by a test and the evaluator). The candidate plan notice now says "Ask4Mo does not currently process live payments or offer checkout" (8 locales); the old claim of no payments or invoices in the account was removed because internal mock records can exist.

## 17. Commercial-term versioning
A price change creates a new immutable version, retires the previous active one in the same transaction, and keeps history. Invoices keep their own amount and currency snapshots.

## 18. Price second-approval workflow
A billing administrator requests terms (`platform.plans.price.change`); a DIFFERENT active administrator holding that permission approves or rejects. Approval, retirement of the old version, creation of the new one and both audit rows are one transaction (audit failure rolls it all back). One pending request per plan version.

## 19. No self-approval
Enforced in the service, by a CHECK constraint (`decided_by <> requested_by`) and by the UI (the requester sees "A second approver is required"). No platform_admin bypass, no override, no break-glass. An inactive approver or one without the permission is refused.

## 20. Customer mirror
`billing_customers`: provider (mock), provider customer reference, user XOR workspace, state. One per provider and subject. No card, address, tax id or bank data.

## 21. Provider-subscription mirror
`billing_provider_subscriptions`: provider reference, customer, plan version, optional commercial-terms reference, provider state (trialing, active, past_due, cancelled), period and grace metadata. Named apart from the W10.4 `subscriptions` table on purpose.

## 22. Billing vs product subscription
Provider state is informational. A `past_due` mirror never revokes access; a `cancelled` mirror never ends the W10.4 subscription (tested: the product subscription stays active).

## 23. Invoice model
`billing_invoices`: provider reference, customer, due and paid amounts, currency, state (open, paid, past_due, void), period and due dates. No PDF, card, tax or raw payload. Labelled MOCK everywhere.

## 24. Payment model
`billing_payments`: provider reference, invoice, amount, currency, status (pending, succeeded, failed) and a bounded safe failure category (declined, insufficient_funds, expired, processing_error, unknown). No instrument details.

## 25. Failed-payment and grace semantics
A failed payment marks the invoice past due and a provider subscription can carry `grace_until`. Both are display metadata; no suspension policy exists and entitlements are unchanged.

## 26. Refund model
`billing_refunds`: provider and refund reference, payment, amount (greater than zero), currency, state (pending, succeeded, failed), approval reference, unique idempotency key. MOCK only: no real money moves. Validation: succeeded mock payment, matching currency, amount not above what remains unrefunded (pending refunds reserve their amount), checked at request and again at approval.

## 27. Refund second approval
`platform.billing.refund` to request, a DIFFERENT administrator with the same permission to approve or reject. Approval creates the pending refund and queues the job; a compensating step fails the request cleanly if the job cannot be queued.

## 28. Refund idempotency
The refund job calls the provider with the stable key `refund:<approval id>`. Tested crash window: the provider acts, the worker dies before the local update, the lease expires, a second worker replays; there is one refund row, one provider refund id, the amount counts once and the job ends succeeded with two attempts. A completed refund replays as a no-op; a rejected or exhausted attempt is recorded as failed with an audit event.

## 29. Billing-event model
`billing_events`: provider, provider event id (unique per provider), event type, NORMALISED fields (allowlist per type, no raw body), state (received, processed, failed), timestamps. Types: customer_created, subscription_updated, invoice_opened, invoice_paid, payment_succeeded, payment_failed.

## 30. Event idempotency
Ingestion is unique on (provider, provider event id), including under concurrent duplicates; every upsert is keyed on provider references, so a duplicate event never duplicates an invoice, payment or subscription update; a processed event replays as a no-op.

## 31. Webhook and future-provider boundary
There is no public webhook, mock or otherwise. A future live adapter would verify the provider signature, normalise the event and call the same ingestion service; the processing pipeline is already idempotent and job-based.

## 32. W10.9 job use
`billing_process_event` (event id only) and `billing_refund` (refund id only). Strict payload schemas, bounded retry, safe failures, not Admin-enqueueable. No scheduler, renewal, polling or reconciliation exists.

## 33. No card data
No card, expiry, bank, tax or raw provider column exists (schema, API schemas, Playwright and evaluator guards; harmless fields such as `payment_id` are allowed).

## 34. No checkout
No checkout, payment-method, billing-portal or candidate billing route exists (route introspection and a frontend scan).

## 35. Coupons decision
Deferred (Post-Capstone in the capability matrix). No promo codes, discount maths or redemption.

## 36. Admin Billing UI
`/admin/billing`: a prominent "MOCK BILLING - NOT LIVE BILLING" banner with provider and live=no, overview counts, commercial terms with request form, approval requests, mock invoices, mock payments with refund request, mock refunds, and provider customers and subscriptions. English only, permission-driven, accessible dialogs with Cancel focused.

## 37. Permissions
Existing canonical permissions only (still 43): `platform.billing.read` (reads), `platform.plans.price.change` (request and decide price changes), `platform.billing.refund` (request and decide refunds). Approve and reject are separate routes per action so `billing.read` can decide nothing. `billing_admin` holds all three; `platform_admin` (plans read and manage, no billing permission), support, knowledge, operations and security hold none. No `platform.billing.manage` was invented and no Admin route creates money (invoices, payments and events enter only through the provider boundary).

## 38. Audit
admin.billing_price_change_requested / _approved / _rejected, admin.billing_price_activated, admin.billing_refund_requested / _approved / _rejected / _executed / _failed. Context: approval, plan version, terms version, payment and refund ids, amount minor, currency and states; no instrument, reason text or provider payload.

## 39. Privacy, export and deletion
The candidate's self-service export gains a clearly simulated `billing_mock` section (states, amounts, currency; no provider ids, no approval workflow). Account deletion removes the user's mock customer, provider subscriptions, invoices, payments and refunds, and a deleted workspace's mock mirrors; shared plan and terms definitions stay. No Admin export, no content browser, no retention claim: real-provider financial retention would need its own legal and provider design.

## 40. Command Center
Mock counts only (open and past-due invoices, failed payments, pending approvals), labelled mock.

## 41. No revenue reporting
No MRR, ARR, LTV, churn or revenue figure is computed (W10.12 owns reporting).

## 42. Migration
`0021_billing_admin` (from `0020_privacy_legal_admin`): eight tables with CHECKs (amount range, currency form, interval, visibility, states, user XOR workspace, no self-approval), unique provider references and events, one-active-terms and one-pending-request partial indexes, and list indexes. Schema only. Fresh, from-0020, constraint and round-trip tests pass.

## 43. Backend tests
**2829 passed, 4 skipped, 0 failed, 0 errors** (baseline 2804/4). 24 new tests in `tests/test_billing_w10_5.py`; two existing guards updated for the Billing schemas and job types. Skips: live Adzuna, Streamlit render, RAGAS and the PostgreSQL job-claim test (needs `TEST_POSTGRES_URL` and a driver).

## 44. Frontend tests
703 unit tests in 84 files (11 new): MOCK banner, live=no, configuration error, terms and history, request validation, second-approval states and self-approval control absence, invoices, payments, refunds, read-only role, no role names, no card fields, candidate no-purchase scans, and 8-locale notice and export copy. Typecheck, lint and build clean.

## 45. Playwright
**212 passed** (211 baseline plus the mock-billing journey: banner, terms request, no self-approval, a different administrator approves, refund request, second approval, a worker executes it). It uses a stateful stand-in with the test acting as the worker; the real worker, provider and replay are proven by the backend tests and the manual QA.

## 46. Evaluators
**36 of 36** CI evaluators pass including the new `scripts/eval_admin_billing.py` (29 checks). The entitlement evaluator was narrowed to the plan code (commercial schemas now live in a separate Billing block) and now allows copy that SAYS there is no checkout. Only the CI set was run.

## 47. Isolation
Temp databases, the mock adapter, temp job runtime, no network. The dev-store fingerprint, schema, checkpoint store, Chroma and research cache are unchanged; `evaluations/` untouched.

## 48. Manual QA
Fresh migrated database, API and a separate worker, mock provider explicitly enabled, data created by the service tooling (no Admin money route). Defaults: MOCK banner, live=false, every plan unconfigured, zero rows. A billing admin proposed terms; the same admin and a support operator were refused; a second billing admin approved; version 1 became active. The candidate's entitlements were identical before and after the price change, the provider `past_due` mirror, the failed payment, the refund and replay. Invoices, a succeeded and a failed payment (declined) and grace metadata showed. A refund request could not be approved by its requester; the second admin approved; it stayed pending until the worker ran, then succeeded once (700 of 2000, refundable 1300); a replay changed nothing. No response contained card or payment-method fields; the candidate had no billing route and was denied Admin billing; the export carried a simulated section; audit rows held ids and states only. Production plus mock reported disabled with the reason. No live call.

## 49. Performance
First Load JS: `/admin/billing` 116 kB, shared 103 kB unchanged; no provider SDK ships to the browser. Indexes: invoices by state and time, payments by status and time, one pending approval per target and approvals by status and time, unique provider events, one active terms row per plan version.

## 50. Dependencies
None.

## 51. Alembic head
`0021_billing_admin` (single head).

## 52. External calls
0 live and 0 paid. The mock adapter makes no network call (asserted with network blocked).

## 53. SEC-W10-05
Remains OPEN for W10.11. Nothing here is a platform pause.

## 54. W10.7 handoff
BillingProvider, the mock adapter, commercial terms, billing metadata, the bounded second-approver pattern and the event and job primitives. W10.7 can reuse the request-then-different-approver design for model activation without changing billing semantics.
