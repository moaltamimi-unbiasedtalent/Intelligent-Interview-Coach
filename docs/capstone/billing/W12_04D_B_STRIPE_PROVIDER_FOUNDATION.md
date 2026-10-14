# W12.4D-B - Stripe Managed Payments provider foundation

**Status: CODE QUALIFIED (deterministic, offline) - STRIPE MANAGED PAYMENTS FOUNDATION COMPLETE - SANDBOX AND SELLER ELIGIBILITY UNVERIFIED.** This wave is the technical foundation only: no Stripe call of any kind was made (not even a sandbox call), no account was created, and there is no checkout, no payment endpoint, no webhook receiver, no subscription, no refund handling and no live billing. Live billing is a code constant that is off.

Starting point: `main` at `89a03644d07d79a911321e02c93b8ed4039909e2` (W12.4A, B, C and the W12.4D assessment/selection merged; PRs #154, #155, #156), clean tree, Alembic head `0027_email_attempts`. Branch `feat/w12-04d-b-stripe-managed-payments-foundation`. Owner-selected provider: **Stripe Managed Payments (primary), Paddle (fallback).**

## 1. Existing billing architecture (verified against the code before any change)
`BillingProvider` protocol exposed only `capabilities()` and `refund()`; one adapter, `MockBillingAdapter` (offline, deterministic, refused outside development and test). Eight `billing_*` tables, immutable commercial terms (none seeded), two-person approvals for price changes and refunds, six normalised event kinds with idempotent ingest on `(provider, provider_event_id)`, two W10.9 jobs, 15 `/admin/billing` routes, a mock-labelled Admin screen, no candidate checkout and no public webhook route. Billing never touches subscriptions or entitlements. All of this is unchanged and still passes its tests.

## 2. What was added
| Piece | Where | Notes |
|---|---|---|
| Provider selector (allow-list) | `policy.SELECTABLE_PROVIDERS = (mock, stripe_managed_payments)`; `provider.resolve_mode` | any other `BILLING_PROVIDER` value raises and `safe_mode` reports DISABLED with the reason; default is disabled |
| `StripeManagedPaymentsProvider` | `src/billing/stripe_provider.py` | implements the existing protocol; `capabilities()` reports checkout, refund, payment methods and tax as false; **`refund()` raises `ProviderRejected` and never reaches a client**; no mock success for an unbuilt operation |
| Credential slots | integration registry `stripe_managed_payments` (10th integration, category "Payments / billing") | four SEPARATE slots: sandbox secret key, sandbox webhook signing secret, live secret key, live webhook signing secret (external names `STRIPE_SANDBOX_SECRET_KEY`, `STRIPE_SANDBOX_WEBHOOK_SECRET`, `STRIPE_LIVE_SECRET_KEY`, `STRIPE_LIVE_WEBHOOK_SECRET`); live slots optional and inert |
| Client factory | `build_stripe_client` | explicit per-client configuration, sandbox only, pinned API version, `max_network_retries=0`, bounded timeout, never the SDK's global `stripe.api_key`, deterministic fake injection, constructing it makes no network call |
| Safety rail for W12.4D-C | `require_managed_payments` | refuses any Checkout Session parameter set without `managed_payments.enabled = true`, so Ask4Mo can never accidentally become an ordinary merchant of record |
| Bounded readiness | `readiness()` + `GET /admin/integrations/stripe_managed_payments/readiness` + Admin panel | fixed states only (below) |
| Error mapping | `map_stripe_error` | any SDK exception reduced to a bounded category; the message (which may embed ids or keys) is discarded |
| Env validation | `env_validation` | an unknown `BILLING_PROVIDER` or `STRIPE_ENVIRONMENT` is critical in hosted environments; selecting live only warns (it cannot enable anything) |
| Dependency | `stripe>=16,<17` (installed 16.0.0) | imported lazily inside functions, never at module import |

## 3. Supported and unimplemented capabilities
Supported: selection, credential resolution, environment separation, readiness reporting, a safely constructed client, the Managed Payments parameter guard. **Not implemented (fail closed):** checkout, subscription purchase, payment confirmation, customer portal, product catalog, webhook receiver and signature verification, event ingestion for Stripe (a Stripe event is refused by `record_event` because `policy.PROVIDERS` stays `("mock",)` and `billing_customers` pins the provider), refunds through Stripe, reconciliation, any entitlement change.

## 4. SDK and API version
Python SDK **stripe 16.0.0** (PyPI, requires Python 3.9+ and `requests`). It pins Stripe API version **`2026-09-30.endive`**, which this code pins explicitly and a test compares with the SDK constant so an SDK upgrade becomes a reviewed change. Stripe's Managed Payments set-up guide requires API version `2025-03-31.basil` or later. The SDK 16.0.0 carries the `managed_payments` Checkout Session parameter (`SessionCreateParamsManagedPayments`), has built-in webhook signature verification with a timestamp tolerance, and supports per-client configuration (`StripeClient(api_key, stripe_version=..., max_network_retries=..., http_client=...)`). No undocumented behaviour is used.

## 5. Managed Payments contract evidence (for W12.4D-C)
From Stripe's Managed Payments documentation: create a Checkout Session with `mode=subscription` and `managed_payments[enabled]=true`; products and prices need an approved tax code (for example `txcd_10103000` SaaS personal use or `txcd_10105001` AI as a service, personal use) and the product must be a fully automated digital product; the seller must accept the Managed Payments terms in the Dashboard and pass an eligibility review; do not rely on the success redirect, use webhooks (`checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed` are the Checkout events listed); tax behaviour comes from the price (exclusive unless configured, a commercial display decision); for subscriptions created this way `subscription.default_payment_method` cannot be updated through the API. The sandbox page describes test cards and a test mode for Managed Payments, but **availability in the owner's own sandbox is not verified**, so the status is SANDBOX ACCESS UNVERIFIED and nothing was called.

## 6. Environment separation and live safeguards
- The default environment is **sandbox**; `STRIPE_ENVIRONMENT` accepts only `sandbox` or `live`, anything else is an error.
- Only the selected environment's slots are ever read. A key that looks like the other environment (`sk_live_` in a sandbox slot) is refused as `credential_environment_mismatch`; a malformed key or webhook secret is `credential_format`; there is no cross-environment fallback.
- Selecting `live` yields **LIVE BILLING DISABLED** and no client can be built (`policy.LIVE_BILLING_ENABLED = False` is a code constant, not a setting). Live slots may be stored (they are inert) and the readiness reports that they are populated.
- Nothing activates at startup: the Stripe mode is never "enabled" and has no operation to run. The mock adapter remains refused in production.

## 7. Credential resolution
Through the W12.4B `LayeredSecretStore`: Admin-managed encrypted value, then environment fallback, then not configured; nothing is copied; values are write-only; rotation needs `platform.integrations.secret.rotate` plus a fresh step-up (a test proves `operations_admin` and `billing_admin` get 403 and the owner needs step-up). Reading a credential value is confined (evaluator allow-list adds only `src/billing/stripe_provider.py`). The reading of the Stripe key prefix happens inside the module and only booleans leave it.

## 8. Admin readiness
States (bounded): `not_configured`, `configured_not_tested`, `sandbox_access_unverified`, `configuration_error`, `provider_unavailable`, `eligibility_not_confirmed`, `live_disabled`. Today's reachable outcomes: not configured, sandbox access unverified (credentials present and well formed, never called), configuration error (mismatch or format), live disabled. **There is no healthy state and no "merchant of record approved" state**; eligibility, merchant of record and sandbox access are always reported as not confirmed/unverified, checkout/refunds/webhooks as not implemented, live billing as disabled. The panel sits on the existing integration detail page (no new Admin section) and the Admin Billing banner now names the provider honestly. Readable with `platform.integrations.read` (platform_admin, operations_admin); `billing_admin` does not hold it and gets 403. 43 permissions unchanged.

## 9. Financial approvals (preserved)
Seller-initiated refunds and commercial price changes keep their two-person approvals unchanged. **Provider-initiated actions are different and must be recorded in W12.4D-D:** when Stripe has already refunded, cancelled or lost a dispute, the fact exists whatever Ask4Mo thinks; after webhook authentication and reconciliation Ask4Mo must represent it accurately, and two-person approval cannot reverse or suppress it. The entitlement service then applies approved business rules to the verified local billing state. No entitlement change exists in this wave.

## 10. Billing event preparation (proposal for W12.4D-D)
Today's kinds: `customer_created`, `subscription_updated`, `invoice_opened`, `invoice_paid`, `payment_succeeded`, `payment_failed`. Proposed Stripe mapping and additions (no migration now):
| Stripe event (candidates) | Normalised event | Status |
|---|---|---|
| `checkout.session.completed`, `customer.subscription.created` | `customer_created` + `subscription_updated` (new: `subscription_created`) | extend |
| `invoice.paid`, `invoice.payment_succeeded` | `invoice_paid`, `payment_succeeded` | exists |
| `invoice.payment_failed` | `payment_failed` | exists |
| `customer.subscription.updated` (renewal, plan change, `cancel_at_period_end`) | `subscription_updated` (+ new field `cancel_at_period_end`) | extend |
| `customer.subscription.deleted` (cancelled, expired, deletion request) | new `subscription_cancelled` with a cause (customer, seller, provider, expired, data deletion) | new |
| `charge.refunded` / refund objects | new `refund_completed` (provider-initiated refunds must be ingestible, with amount and currency) | new |
| `charge.dispute.created` / `closed` | new `dispute_opened`, `dispute_resolved` | new |
Needed storage changes (D): allow the Stripe provider value in the `billing_*` constraints, a `billing` subscription source, event ordering fields, parked/retry state.

## 11. Webhook design (documented, not built)
One public POST route; read the raw body first (size-limited); verify the `Stripe-Signature` header with the signing secret of the CURRENT environment using the SDK's verification (constant time, timestamp tolerance), reject anything else with a generic 400 and persist nothing; deduplicate on the Stripe event id (existing unique key); persist the normalised event transactionally and process in the W10.9 job with bounded retries and backoff and the existing failure visibility (manual retry, Admin failure list); guard ordering with the object version or event time so an older event cannot overwrite a newer one; reconcile against Stripe after downtime (read-only first); a redirect or client-submitted checkout id is never proof; live and sandbox webhook secrets never cross.

## 12. Entitlement boundary
No change to entitlements. Premium access can never come from a success redirect, an unverified payment status, a client-submitted checkout id, provider readiness or mock events. `src/billing` contains no reference to subscription or entitlement models (a test enforces it). The future bridge (W12.4D-D) is an explicit, audited, owner-policy-driven translation of verified local billing state.

## 13. Managed Payments customer experience (constraints for later UI)
Link is the seller of record shown to the customer (statement descriptor `LINK.COM* ...`); payment receipts, invoices, refund notices and subscription emails come from Link and Ask4Mo's receipt settings do not apply; customers manage and cancel subscriptions and payment methods in their Link account (a redundant Ask4Mo portal should not be built without checking the lifecycle; an optional Stripe customer portal exists); **custom checkout domains are not supported**; adaptive pricing (local currency display) is on by default; Stripe may refund within 60 days or after 48 hours without a seller reply; a customer's deletion request through Link cancels subscriptions and deletes data from Stripe objects in the seller's account (the local mirror must tolerate this).

## 14. Payment methods and geography
Per the Managed Payments documentation fetched in W12.4D-A: cards, Apple Pay, Google Pay and Link are supported globally including recurring; regional methods listed are US, Korea, India, Brazil and Belgium (Bancontact, one-time only). **SEPA Direct Debit, iDEAL and PayPal are not listed and must not be assumed**: for German consumers that is a real limitation to decide on before launch (accept it, or revisit Paddle). Blocked buyer countries: Ascension Island, China, Cuba, Iran, Kosovo, North Korea, Russia, Syria, Tristan da Cunha. No country-policy engine is built; Ask4Mo's supported-country decision remains open.

## 15. Fees (verified rules; no runtime estimates)
3.5% per successful Managed Payments transaction, on top of standard Stripe processing fees (EEA standard cards 1.5% + EUR 0.25 on the Germany page) and applicable Stripe Billing fees; the fee is on the full transaction amount including indirect tax. Whether Billing fees stack and how the 3.5% is treated on refund still need Stripe's confirmation. No fee figure is hard-coded into any runtime calculation.

## 16. German seller eligibility (owner prerequisites; none completed)
The legal seller entity; Stripe account onboarding; Managed Payments terms accepted and access confirmed through Stripe's eligibility review (business type and region; direct integration only); an eligible tax code for the product (SaaS or AI as a service) and fully automated delivery (no live human coaching); Stripe's general prohibited and restricted businesses list reviewed; tax and accounting documentation. Ask4Mo does not claim any of this is done.

## 17. Commercial decisions still open
Premium price, annual price, trials, cancellation rules, refund policy, grace period after a failed payment, supported countries, B2B billing, tax-inclusive versus tax-exclusive display. The frontend's EUR 19.99 is a preview: nothing was seeded into `billing_commercial_terms` and no Stripe price was created.

## 18. Privacy
No card data, no card form; provider-hosted collection only in the later checkout wave; minimal billing personal data; no Stripe secret in any frontend bundle; deletion and export hooks unchanged.

## 19. Database
**No migration.** Nothing persisted is required by the foundation (credentials use the existing `managed_secrets` table). Alembic head stays `0027_email_attempts`; the normal developer database was not touched.

## 20. Test results
`tests/test_stripe_foundation_w12_4d_b.py` (37 tests, all non-loopback network blocked): allow-list and unknown-provider rejection, mock regression and production refusal, sandbox/live handling and the live-disabled constant, default deployment and env validation, four-slot registry, readiness matrix (nine cases, never healthy or approved), environment separation and managed-over-environment precedence, client factory (per-instance, pinned, unretried, never global), live and unknown environments never build a client, error mapping without messages, truthful capabilities and fail-closed refund, the Managed Payments guard, Stripe events refused with no entitlement change, no checkout, webhook, payment or portal route, Admin permission matrix, step-up and secret non-disclosure. Existing billing, integration, secret-store and email tests were updated only where they pinned "mock-only" or "no billing provider". Frontend: 9 unit tests and 9 Playwright tests (states, role boundary, responsive at 1280, 768 and 390 in light and dark).

## 21. Operator prerequisites and sandbox limitations
Owner: create the German-entity Stripe account; accept the Managed Payments terms; confirm eligibility and an eligible tax code; create sandbox keys; enter them only through Admin (step-up); separately authorize any external test. Until then the state is SANDBOX ACCESS UNVERIFIED and ELIGIBILITY NOT CONFIRMED. Sandbox availability of Managed Payments for the owner's account and webhook parity are unconfirmed.

## 22. Handoff to W12.4D-C
Needs the owner decisions in section 17 (at least price, tax display and country scope), a confirmed sandbox, a sandbox authorization, an eligible tax code, and a decision on the missing SEPA/PayPal methods. W12.4D-C then adds the server-side Checkout Session creation (with `require_managed_payments`), product and price mapping (probable migration), and the return page that only polls local state. Release dependencies that remain visible: W12.4C live Brevo validation (deferred), the research-cache evaluator isolation fix before integrated requalification, W12.4F cached-provider restart handling.
