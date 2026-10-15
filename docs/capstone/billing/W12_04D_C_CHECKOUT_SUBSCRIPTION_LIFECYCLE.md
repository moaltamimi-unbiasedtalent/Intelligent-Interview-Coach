# W12.4D-C - Checkout and subscription lifecycle foundation

**Status: CODE QUALIFIED (deterministic, offline) - CHECKOUT AND SUBSCRIPTION LIFECYCLE FOUNDATION COMPLETE - PROVIDER TRANSACTIONS DISABLED - WEBHOOK AND ENTITLEMENT INTEGRATION PENDING.** No Stripe call of any kind was made (not even a sandbox call), no Stripe account, product or price was created, no payment was taken, live billing is a code constant that is off, and a new code constant (`EXTERNAL_CHECKOUT_AUTHORIZED = False`) keeps even a sandbox checkout impossible by configuration. No webhook receiver, no paid entitlement and no refund execution exist. Stripe Managed Payments eligibility and sandbox access remain **unverified**; billing is **not production-ready**.

Starting point: `main` at `29d5fe19f148793313a83dea95d0efee2619cb5d`, Alembic head `0027_email_attempts`. Branch `feat/w12-04d-c-checkout-subscription-lifecycle`. New head: `0028_checkout_sessions`.

## 1. Architecture
```
Pricing / Account  ->  POST /billing/checkout-sessions (authenticated, Idempotency-Key)
   ->  CheckoutService (src/billing/checkout.py)
         availability gates (never contacts a provider) -> purchasable plan + ACTIVE immutable commercial terms + ACTIVE provider price mapping
         durable idempotent attempt (billing_checkout_sessions)
   ->  BillingProvider.create_checkout_session()   (interface extended minimally; capabilities(), refund(), mock unchanged)
   ->  StripeManagedPaymentsProvider                 (fail closed; managed_payments.enabled = true; mode = subscription)
   ->  provider-hosted checkout page (Link is the seller of record)
Browser returns to /billing/return?session=<ours>&outcome=...  ->  records a FACT only
```
The candidate sends **only a plan code**. Price, currency, interval, provider, environment, return URLs, idempotency of the provider call and entitlement are server decisions.

## 2. Provider contract
`CheckoutRequest(idempotency_key, provider_price_id, success_url, cancel_url, client_reference_id, expires_at)` and `CheckoutResult(provider_session_id, url, expires_at)`. `BillingProvider.create_checkout_session(request)`:
- **Mock** raises `ProviderRejected("capability_unavailable")`: a candidate is never redirected to a fake processor. Tests inject a fake provider instead; the mock's capabilities still report checkout false.
- **Stripe adapter** refuses `checkout_not_authorized` unless a test injects a client factory or the code constant is true, refuses `live_disabled` outside sandbox, passes `require_managed_payments(params)` (`managed_payments.enabled = true`, `mode = subscription`) before any client is built, calls `client.v1.checkout.sessions.create(params, {"idempotency_key": ...})`, validates the returned id and https URL, and maps any SDK error to a bounded category (timeout, unavailable and rate-limit are `ProviderRetryable`; everything else is `ProviderRejected`). There is **no silent fallback to ordinary Stripe checkout**.

## 3. Candidate journey
Pricing (preview, EUR 19.99 is **not** an approved price) -> account/register -> Account page "Premium subscription" panel -> (only if the server reports checkout enabled) Continue to secure checkout -> provider page -> browser return page -> account shows "waiting for confirmation". States: plan selected, sign-in required, preparing, redirecting, canceled, expired, confirmation pending, status unavailable, provider unavailable. There is **no purchase button when checkout is not enabled** (the default today) and the pages never say "Payment successful", "Subscription active" or "Premium unlocked" (a test scans every locale). The redirect target is re-validated in the browser against an allow-list (`https://checkout.stripe.com`, no credentials) so a malformed response cannot become an open redirect.

## 4. Commercial terms and price mapping
`billing_provider_prices` maps ONE immutable commercial-terms row to the provider product and price per environment (internal plan version via the terms, terms version, provider, environment, product id, price id, interval, currency, status `active|retired`). Amount, currency and interval are snapshots that must **equal** the terms, otherwise the mapping is ignored (`no_price_mapping`). Only terms in state `active` (created through the two-person approval) are purchasable; a retired mapping or retired terms never become the price by themselves; no terms means unconfigured, never free. Nothing is seeded. Registering mappings (Admin or migration tooling) is a later, owner-approved step; this wave only consumes them.

## 5. Persistence
`billing_checkout_sessions`: public id, user (CASCADE), plan version, terms and mapping (RESTRICT), provider, environment, provider session id, status (`pending_creation|open|canceled|expired|failed`), idempotency key, checkout URL (kept **only while open**), provider attempts, failure category, created/expires/last-synced/browser-returned timestamps. No card or payment data, no credential, no webhook secret. Deleted with the account.

## 6. Migration
`0028_checkout_sessions` (down `0027_email_attempts`): creates both tables and indexes, reversible, no `create_all`, no manual stamp, single head (tests, CI Alembic step, evaluators updated from 0027).

## 7. Idempotency and concurrency
- Unique `(user_id, idempotency_key)`; at most **one open attempt per (user, plan version)** (partial unique index `uq_bcs_one_open_per_user_plan`). A different key while an attempt is in flight joins it instead of duplicating.
- The provider idempotency key is **stable per local record** (`ask4mo-checkout-<public id>`), so a retry after a timeout cannot create a second provider session; a retryable failure may be retried with the same key (bounded to 5 attempts); a rejection is terminal for that key and stores no URL.
- A concurrent race is resolved by the unique indexes: the loser re-reads and returns the winner's record or a 409. Keys are owner-scoped, validated (`^[A-Za-z0-9_-]{8,64}$`), and reuse for a different purchase is a 409.
- An elapsed open attempt expires lazily (on create, return and status) and makes room for a new attempt; expiry clears the URL.

## 8. State machine
Four separate dimensions (`src/billing/lifecycle.py`): **checkout** (`none, preparing, open, canceled, expired, failed`), **subscription** (`none, confirmation_pending, active, past_due, cancel_scheduled, canceled, expired`), **payment** (`none, pending, succeeded, failed, refunded, disputed`) and **entitlement** (decided only by `EntitlementService`). Checkout transitions are listed in `CHECKOUT_TRANSITIONS` (terminal: canceled, expired). Every provider-owned subscription or payment state beyond "none/confirmation pending" is refused by `require_evidence` unless authenticated provider evidence backs it; no client, redirect or mock path can pass it. `CHECKOUT_STATUSES` contains **no paid or completed state**. Cancellation causes (customer, seller, provider, expiry, data deletion) are enumerated for D; executing a seller cancellation is later work.

## 9. Security controls
Authenticated, owner-scoped routes (another user's checkout is a 404); `extra=forbid` request models (price, currency, URL, entitlement, provider fields are 422); per-user and per-IP rate limits; return URLs built from the configured trusted origin (`ASK4MO_APP_BASE_URL`, else the first configured frontend origin), https only (http `localhost` only in development), never the Host header; public availability returns only the coarse code `not_enabled`; internal reasons stay in code and audit; no secret, session id URL or provider payload in logs or audit context; audit events `billing.checkout_created|failed|canceled` carry ids and bounded categories only; **there is no payment-success endpoint** (a test asserts the exact route set).

## 10. Managed Payments requirements honoured
`managed_payments.enabled = true` and `mode = subscription` are mandatory and checked before any client is built; Link is the seller of record (receipts and payment emails come from Link, customers manage a paid subscription with Link, Ask4Mo does not store card data and has no custom checkout domain); prices need approved tax codes and the seller must pass Stripe's eligibility review (**not confirmed**); some payment methods and buyer countries (China, Russia, Cuba, Iran, Syria, North Korea, Kosovo and others) are unsupported by Managed Payments; fees are 3.5% plus processing and Billing fees (owner commercial input). All of this is documentation and UI copy, not a promise: nothing was verified against a live account.

## 11. Cancellation, refund and entitlement boundaries
- A candidate who cancels at the provider's page sees "canceled, nothing was charged"; the attempt is closed and the URL cleared.
- Cancelling or refunding a **paid** subscription happens with Link (seller of record). Ask4Mo's two-person refund approvals are preserved unchanged; an external provider refund is an authoritative fact to reconcile in W12.4D-D, never something this wave executes.
- **No entitlement is changed by checkout, redirect, mock or unverified status.** A browser return sets `browser_returned_at` only; the status view reports `entitlement.changed_by_billing = false` and `subscription = confirmation_pending` at most. Entitlements stay `EntitlementService`'s alone; the bridge is a future W12.4D-D, evidence-gated step.

## 12. Tests
`tests/test_checkout_w12_4d_c.py` (54): terms and mapping gates, trusted URLs and origins, idempotency (same key, different key, owner scope, bad keys), concurrency (6 threads, one attempt), retryable/terminal failures, return-as-fact, cancel, expiry, status, cascade, state machine and evidence requirement, no paid status, adapter fail-closed and parameter shape (injected fake client), HTTP authorization/extra-field/no-endpoint tests, migration shape. Frontend `tests/checkout-w12-4d-c.test.tsx` (20): URL allow-list, idempotency key shape, no button when unavailable, untrusted redirect refused, retry reuses the key, pending/canceled/unavailable states, no success wording in any locale. All provider objects are fakes and every non-loopback socket fails the test. Head pins moved to 0028 in the migration tests and evaluators.

## 13. Limitations
Checkout cannot run: the Stripe adapter reports `checkout: false`, the constant is false, no price mapping exists and no eligibility is verified. No webhook, subscription mirror, invoice, tax display, trial, proration, customer portal link, seller cancellation or refund execution. Admin cannot yet register price mappings. The browser cannot learn the final result of a purchase.

## 14. Sandbox prerequisites (owner actions, not done)
Stripe account with Managed Payments eligibility accepted; sandbox access confirmed; product and price created with an approved tax code; sandbox key and webhook secret stored through the W12.4B slots; owner-approved commercial terms (two-person approval); a price mapping registered; a deliberate change of `EXTERNAL_CHECKOUT_AUTHORIZED` in a reviewed change.

## 15. Owner decisions still open
Monthly and annual price, currency and tax-inclusive display, trial, cancellation and refund policy, grace period, countries, B2B, legal seller entity, Managed Payments eligibility, whether to offer annual billing.

## 16. W12.4D-D handoff
Webhook receiver with signature verification and timestamp tolerance; Stripe events into `billing_events` (extend `policy.PROVIDERS`, a reviewed change); verified evidence into `lifecycle.require_evidence`; subscription and payment mirrors; reconciliation of external refunds; the evidence-gated bridge to `EntitlementService`; Admin view of checkout attempts and price mappings.
