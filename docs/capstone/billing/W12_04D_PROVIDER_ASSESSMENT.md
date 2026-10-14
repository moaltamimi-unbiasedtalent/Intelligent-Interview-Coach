# W12.4D Phase A - Live billing provider: architecture audit and provider selection

**Status: ASSESSMENT COMPLETE - AWAITING OWNER PROVIDER SELECTION.** This phase is documentation only. No provider code, account, credential, checkout, subscription, refund or webhook registration was created or contacted, and no payment of any kind was initiated.

Starting point: `main` at `719fa9eacd772421cfe03b5120f39ac23b65930d` (W12.4C merged as PR #155), clean tree, Alembic head `0027_email_attempts`. W12.4A, W12.4B and W12.4C are present on main. Branch: `feat/w12-04d-billing-provider-assessment`.

Research note: provider facts below were taken from the providers' own pages during this phase (linked in section 6). Marketing pages are vendor claims, several pages did not state exact current terms, and fee figures and country lists change. Every number is labelled with its uncertainty and **must be re-confirmed on the provider's live page before the owner commits**.

## 1. Current-state audit (from code)
| Layer | What exists | State |
|---|---|---|
| `BillingProvider` protocol (`src/billing/provider.py`) | `name`, `live`, `capabilities()`, `refund(idempotency_key, provider_payment_id, amount_minor, currency)` only | IMPLEMENTED (deliberately minimal) |
| Provider adapter | exactly one: `MockBillingAdapter` (offline, deterministic, records calls for idempotency tests). `resolve_mode` fails closed: any provider other than `disabled`/`mock` raises, and mock is refused outside development/test environments | MOCK-ONLY |
| Billing domain tables | `billing_commercial_terms`, `billing_approval_requests`, `billing_customers`, `billing_provider_subscriptions`, `billing_invoices`, `billing_payments`, `billing_refunds`, `billing_events` (migration `0021_billing_admin`) | IMPLEMENTED (metadata mirror; mock data) |
| `BillingService` (`src/billing/service.py`, 633 lines) | versioned immutable commercial terms; dual-control price-change and refund approvals (second, different administrator with the specific permission); idempotent event ingest on `(provider, provider_event_id)`; `process_event` applies six normalised event kinds; refund execution through a stable idempotency key; account and workspace deletion; user export | IMPLEMENTED, exercised only with the mock |
| Normalised events | `customer_created`, `subscription_updated`, `invoice_opened`, `invoice_paid`, `payment_succeeded`, `payment_failed` (`policy.EVENT_TYPES`) | PARTIAL (no refund, dispute, cancellation or `cancel_at_period_end` events) |
| Jobs (`src/billing/jobs.py`) | `billing_process_event`, `billing_refund` on the W10.9 queue (id-only payloads, lease-guarded, idempotent) | IMPLEMENTED |
| Admin API (`/admin/billing/*`, 15 routes) | overview, terms, approvals, price-change request/approve/reject, invoices, payments, refunds, customers, refund request/approve/reject. Permissions: `platform.billing.read`, `platform.billing.refund`, `platform.plans.price.change` | IMPLEMENTED, labelled MOCK BILLING |
| Admin UI | `BillingView.tsx` (MOCK banner, terms, approvals, payments, refunds) | IMPLEMENTED (mock) |
| Candidate billing API | **none.** There is no checkout, portal, invoice or billing route for candidates. The only candidate plan surface is `GET /auth/plan` (read-only) | NOT IMPLEMENTED |
| Webhook endpoint | **none.** Events can only be ingested internally (`ingest_event`); there is no public HTTP route, no signature verification | NOT IMPLEMENTED |
| Checkout, payment methods, tax, hosted portal, coupons | explicitly not built (`provider.py`, `W10_5_BILLING_PAYMENT_ADMINISTRATION.md`) | NOT IMPLEMENTED |
| Marketing/pricing page | shows Basic EUR 0 and Premium EUR 19.99 as **preview**; `BILLING_ENABLED = false`; the Premium CTA links to `/register?plan=premium`, which the frontend ignores, so there is no purchase path | PRESENTATION ONLY |

Nothing in the billing system is operational: it is a tested, dual-controlled metadata mirror around a mock.

## 2. Architecture (corrected to the code)
```
Frontend (/pricing, /account plan view)  --  no purchase path today
   |  GET /auth/plan (read-only)
   v
Auth/plan API ----> EntitlementService  <---- plans, plan_versions, plan_entitlements, subscriptions
                         (decides access: source = system_default | migration | admin)

Admin UI (/admin/billing) -> Admin Billing API (/admin/billing/*, require_permission)
   -> BillingService  (terms, approvals, events, refunds; NEVER touches subscriptions/entitlements)
        -> BillingProvider protocol -> MockBillingAdapter (offline)          [no live adapter]
        -> billing_* tables (customers, provider subscriptions, invoices, payments, refunds, events)
        -> W10.9 jobs: billing_process_event, billing_refund
   (no public webhook route; no candidate checkout route)
```
Billing state and entitlement state are **separate by construction and by test** (`BillingService` imports no subscription or entitlement model). The only way a candidate's access changes today is an administrator assigning a plan (`PlanRepository.assign`, source `admin`).

## 3. Billing versus entitlements (to be preserved)
- **Billing** (provider-facing): payment processing, provider subscriptions, invoices, refunds, payment status, customer billing data. Mirrored read-mostly in `billing_*`.
- **Entitlement** (product-facing): feature access and limits from the active `Subscription` -> `PlanVersion` -> `PlanEntitlement`. `EntitlementService` is the sole authority, and its fallback is Basic (never Premium).
- **Rule for every future wave:** the provider is never an authorization source. A verified, idempotent, server-side translation step (billing event -> proposed subscription change) is the only bridge, it must be explicit, audited, reversible and policy-defined by the owner (grace period, failed payment behaviour), and it never reads a browser callback. Today no such bridge exists and none was built in W10.5 on purpose.

## 4. Commercial model (only what code and docs establish)
| Topic | Established | Status |
|---|---|---|
| Plans | `basic` and `premium` (Premium (preview)); Premium adds only `premium_preview` | DECIDED (code) |
| Display prices | Basic EUR 0, Premium EUR 19.99 as marketing constants; annual ~EUR 199 is an internal hypothesis, deliberately not public | PRESENTATION ONLY; **UNDECIDED commercially** |
| Stored prices | `billing_commercial_terms` supports `amount_minor`, `currency`, `interval` (month/year), `trial_days` (max 365), `visibility`; **no row is seeded: every plan is UNCONFIGURED** | UNDECIDED |
| Currencies | EUR displayed; schema accepts any ISO code; no multi-currency policy | UNDECIDED |
| Monthly / annual | schema supports both; only monthly displayed | UNDECIDED |
| Trials | field exists; no policy, no trial logic | UNDECIDED |
| Cancellation, upgrade, downgrade, proration | not implemented, no policy | UNDECIDED |
| Refunds | internal dual-control refund flow exists (mock); no refund policy text | PARTIAL; policy UNDECIDED |
| Country availability / geo restrictions | none defined | UNDECIDED |
| B2C versus B2B, business invoices, VAT numbers | not modelled; workspace-level subscriptions and customers exist in the schema | UNDECIDED |
| Coupons, discounts | deliberately absent | UNDECIDED |
| Legal documents (terms, privacy, AI transparency) | versioned and published; no billing terms, no statutory cancellation/withdrawal text | UNDECIDED (legal) |

## 5. Gaps against a real provider (lifecycle)
| State or transition | Today | Gap |
|---|---|---|
| checkout initiated / completed | none | candidate checkout route, hosted checkout session, return page that only polls local state |
| payment failed | event recorded, invoice -> `past_due`, no access change | dunning/retry policy, notification, grace-to-downgrade policy |
| subscription active / renewal | `subscription_updated` mirrors provider state | mapping of provider subscription to the local `Subscription` (new source value), period handling |
| cancel at period end / immediate cancel | provider state `cancelled` only | `cancel_at_period_end` and effective date, candidate self-service cancel |
| upgrade / downgrade | none | proration policy, plan mapping in both directions |
| refund | admin-initiated mock refund | provider-initiated refund events, partial refund reconciliation |
| dispute / chargeback | none | event kinds, evidence handling, entitlement policy |
| expired subscription | none | scheduled expiry, grace, downgrade to Basic |
| provider outage | job retry/backoff for refunds and events | checkout outage UX, reconciliation after downtime |
| out-of-order / duplicate events | duplicates are idempotent; ordering is not modelled | event ordering/version guard (`occurred_at` or provider sequence) |

## 6. Provider evaluation
Sources used (official pages): [Stripe pricing Germany](https://stripe.com/en-de/pricing), [Stripe Billing pricing](https://stripe.com/en-de/billing/pricing), [Stripe Tax pricing](https://stripe.com/en-de/tax/pricing), [Stripe Managed Payments pricing](https://support.stripe.com/questions/managed-payments-pricing), [Paddle pricing](https://www.paddle.com/pricing), [Paddle supported countries](https://developer.paddle.com/concepts/sell/supported-countries-locales/), [Paddle seller countries](https://www.paddle.com/help/start/intro-to-paddle/which-countries-are-supported-by-paddle), [Mollie recurring](https://docs.mollie.com/docs/recurring-payments), [Mollie webhooks](https://docs.mollie.com/reference/webhooks), [Mollie next-gen webhooks](https://docs.mollie.com/reference/webhooks-new), [Mollie pricing](https://www.mollie.com/pricing).

| Criterion | Stripe Billing | Paddle | Mollie |
|---|---|---|---|
| Model | payment processor; Stripe Billing for subscriptions; **Stripe Tax** (calculate/collect; registration and filing only in the paid "Complete" tier); **Managed Payments** is a separate merchant-of-record product (3.5% per transaction on top of processing fees; the fetched page did not state supported seller countries or status, so **Germany eligibility is unconfirmed**) | **merchant of record** (Paddle is the seller; calculates, collects and remits VAT/sales tax, issues the invoice, handles chargebacks) | payment service provider; **not** a merchant of record, no tax engine |
| Germany-based merchant | supported (Stripe has a German entity and pricing page) | German business not on the unsupported-seller list; supports software businesses; account verification applies (details not on the fetched page) | supported (Dutch PSP, strong in the EU) |
| International customers | very broad | 200+ countries and territories, 30 currencies, sanctioned countries blocked; payout currencies limited to USD, EUR, GBP, AUD, CAD | Europe-centric; fewer markets and local methods outside Europe |
| Subscriptions | Stripe Billing: plans, trials, proration, upgrades, cancel at period end, dunning, Customer Portal | built-in subscriptions, checkout, customer portal | Subscriptions API for fixed amounts via mandates; one payment per charge; no subscription status webhook (you track payments by `subscriptionId`); you build portal and proration |
| Payment methods | most extensive (cards, SEPA, wallets, local methods) | cards, PayPal, wallets, some local methods | strong EU (iDEAL, SEPA Direct Debit, Bancontact, cards, PayPal) |
| VAT/tax and invoicing | Stripe Tax: Basic is per transaction (about 0.5% no-code or 0.45 EUR API, listed for Germany); Complete from about 80 EUR/month, 1-year contract; the merchant stays the seller and remains responsible for registration and filing unless Managed Payments applies | included; Paddle is the legal seller to the customer | none; merchant is responsible for VAT, OSS and invoices |
| Fees (headline, verify) | Billing: 0.7% pay-as-you-go (Germany page); standard European cards about 1.5% + 0.25 EUR; plus tax fees | 5% + 0.50 per transaction, all-inclusive (vendor page); custom pricing at scale | cards about 1.8% + 0.25 EUR (consumer EEA); SEPA Direct Debit per-transaction fee about 0.35 EUR (not confirmed for Germany recurring) |
| Webhooks | signed (`Stripe-Signature`, timestamped HMAC; verified by library) and replayable from the dashboard | signed (`Paddle-Signature`, timestamp plus HMAC) with a separate sandbox | classic webhooks carry only an id and you fetch the payment (no signature); **next-gen webhooks** are HMAC-SHA256 signed (`X-Mollie-Signature`) for payments, refunds in beta; subscription payment coverage not confirmed |
| Sandbox | test mode | separate sandbox environment | test mode |
| SDK/API maturity | most mature | good (Python SDK, Paddle.js) | good (official libraries) |
| Operational complexity | highest surface (Checkout, Billing, Customer Portal, Tax, webhooks); you own tax registration and filing | lowest compliance burden; MoR flow changes invoices, refunds and data ownership | most to build; no portal, no tax |

(The webhook header formats for Stripe and Paddle are stated from established provider documentation rather than fetched in this phase; confirm in Phase B.)

## 7. Decision matrix
Scores 1 (poor) to 5 (strong) against Ask4Mo's actual needs (EUR-priced B2C digital subscription, a small team, a German operator, a global audience, a billing mirror that already exists). Weights as proposed.

| Criterion (weight) | Stripe | Paddle | Mollie | Evidence and uncertainty |
|---|---|---|---|---|
| International availability (15) | 5 | 5 | 3 | Stripe/Paddle global; Mollie Europe-centric. Paddle payouts limited to five currencies |
| Subscription functionality (20) | 5 | 4 | 3 | Stripe full lifecycle; Paddle covers it with fewer controls; Mollie leaves portal/proration to Ask4Mo |
| Germany/EU tax and invoicing fit (20) | 3 | 5 | 2 | Paddle as MoR removes VAT/OSS registration and filing and issues invoices. Stripe Tax calculates but the merchant files, unless Managed Payments is available to a German seller (**unconfirmed**) |
| Implementation complexity (15) | 3 | 4 | 2 | Stripe has the largest surface; Paddle the smallest compliance work; Mollie the most custom build. Paddle adds seller approval |
| Payment methods and checkout (10) | 5 | 4 | 4 | Stripe widest; Mollie excellent for EU methods |
| Webhook, reliability, security (10) | 5 | 4 | 3 | Mollie classic hooks are unsigned; next-gen are signed but subscription coverage is unconfirmed |
| Fees and flexibility (10) | 3 | 2 | 4 | Paddle's effective rate on a 19.99 EUR charge is high (5% + 0.50 is about 7.5%); Stripe is cheaper but tax tooling costs extra; Mollie cheapest |
| **Weighted total (out of 100)** | **82.0** | **83.0** | **57.0** | |

**Sensitivity (important):** Stripe and Paddle are a statistical tie. Raising the fee weight to 20 and lowering tax to 10 flips the result (Stripe 82.0, Paddle 77.0). Mollie stays well behind under any reasonable weighting because it provides no tax handling and no portal. The decision therefore turns on one question only the owner can answer: **does the owner want to carry VAT registration and filing (Stripe, lower fees) or hand it to a merchant of record (Paddle, higher fees)?**

## 8. Recommendation
**Recommend Paddle (merchant of record), with Stripe Billing as the credible alternative.**
- **Why Paddle:** Ask4Mo is a small team selling a EUR 19.99 digital subscription to a global audience. The dominant hidden cost is EU and international VAT registration, filing, invoicing and chargeback handling, which a merchant of record absorbs. Paddle also has a separate sandbox, signed webhooks and hosted checkout and portal, so the integration surface and the compliance workload are the smallest, and it fits the existing `BillingProvider` plus normalised-event design.
- **Why not Stripe (first):** the best technology, but at this scale the owner would take on VAT registration and filing (Stripe Tax Complete starts at about 80 EUR/month, or Managed Payments whose German availability is unconfirmed) and a larger integration surface. Choose Stripe if lower fees and full control matter more than outsourcing tax.
- **Why not Mollie:** it would require building the customer portal, plan changes, dunning and the entire tax and invoicing responsibility, and its subscription webhook story is weaker.
- **What it costs in trade-off:** higher percentage fee; Paddle is the seller of record, so it owns the customer invoice and the payment relationship (data minimisation benefit, but less control and branding); refunds, disputes and tax invoices follow Paddle's rules; payouts are in USD, EUR, GBP, AUD or CAD; Paddle approves sellers and products, which must be checked against Ask4Mo's AI-coaching offering and policies.

**Nothing provider-specific will be implemented until the owner approves a provider.**

## 9. Security architecture (for the approved provider)
- **Credentials** only through the W12.4B SecretStore (managed over environment, no backfill, write-only, step-up). Expected slots (names finalised in Phase B): API key, webhook signing secret, and for Paddle a client-side token (public, non-secret). No credential is ever returned by Admin.
- **Authorization** unchanged: the 43 permissions, `platform.billing.*`, `platform.plans.price.change`; `billing_admin` does not gain `secret.rotate`. No new permission unless an actual need is proven.
- **No client-supplied entitlement grants:** checkout creation is server-side for the authenticated owner; the browser may carry only an opaque provider session identifier; success pages poll local state.
- **No unauthenticated billing mutation:** the only unauthenticated route is the webhook, and it mutates nothing until a signature verifies.
- **Card data:** provider-hosted checkout only; no card field, token, last-four or payment instrument is stored by Ask4Mo (the schema already forbids it).
- **Privacy:** store provider reference ids and amounts, not names, addresses or tax ids; keep the existing deletion and export hooks (`delete_billing_for`, `export_for_user`); with a merchant of record the provider is the processor of customer billing details and the privacy documents need updating (owner/legal).

## 10. Webhook design
- **Edge:** one public POST route, raw body read before parsing, size limit, signature check with the provider's documented scheme using constant-time comparison, timestamp tolerance (replay window), then normalisation to the existing event shape. An invalid signature returns a generic 400, writes nothing and is counted for diagnostics.
- **Idempotency:** `(provider, provider_event_id)` uniqueness already exists; duplicates return success without effect.
- **Ordering:** add a monotonic guard (provider event time or object version) so an older `subscription_updated` cannot overwrite a newer one; unknown or out-of-order events park as `received` and are retried by the job.
- **Processing:** persist first, process in the W10.9 job (bounded retries with backoff, manual retry exists), apply local state changes transactionally, audit significant failures, never place a payload or secret in a job.
- **Trust:** an event is trusted only after signature verification AND lookup of the referenced object by id (Paddle/Stripe) or fetch-by-id (Mollie classic), never from a redirect or browser callback.
- **Recovery:** a reconciliation job compares provider state with the local mirror after downtime, flagging differences for Admin (read-only first).

## 11. Admin billing operations
Existing: overview, terms, approvals (dual control), invoices, payments, refunds, customers. A real provider additionally needs: provider readiness (credential source, webhook secret present, last verified event time), webhook failure and replay visibility, reconciliation differences, a "refund via provider" path that reuses the existing approval and job, and clear separation of entitlement-affecting actions (which stay in the Plans/Subscriptions admin). `billing_admin` keeps its current permission set and sees no candidate-private content (customer rows already carry only labels). Test credentials and live credentials must be visibly distinct environments.

## 12. Implementation roadmap (after owner approval)
| Wave | Scope | Notes |
|---|---|---|
| W12.4D-B | Provider adapter, SecretStore slots, mode resolution (`BILLING_PROVIDER` gains the approved provider; the mock guard stays), sandbox-only configuration, readiness in Admin | no checkout yet; extends `BillingProvider` with the minimum new methods; tests with a recording fake provider |
| W12.4D-C | Candidate checkout and subscription lifecycle: server-created checkout session, plan-to-price mapping, return page that polls local state, cancel and portal link | requires owner decisions (section 15) and probably a migration for plan-price mapping and a `billing` subscription source |
| W12.4D-D | Signed webhook endpoint, ordering guard, reconciliation, the explicit billing-event-to-subscription translation with owner-defined grace and failure policy | the only place billing state may propose an entitlement change |
| W12.4D-E | Customer-facing billing page (status, invoices via provider), Billing Admin operations for the real provider, provider-initiated refund and dispute events | privacy/legal text updates |
| W12.4D-F | Security qualification, sandbox acceptance end to end, operator approval gate | no real-money test is authorised in any wave |

## 13. Migration implications (anticipated, to be confirmed in Phase B)
- `subscriptions.source` currently allows only `system_default`, `migration`, `admin` (check constraint): a provider-driven subscription needs a new allowed value (migration).
- A mapping from `plan_versions` and `billing_commercial_terms` to the provider's price or product id (new column or table).
- Checkout-session records (opaque reference, subject, status, expiry) so a return page can be verified.
- Event ordering fields and a parked/retry state for out-of-order events; `cancel_at_period_end`; dispute and refund event kinds (the `EVENT_TYPES` and state check constraints are DB-level in some tables).
- Provider enums in `billing_*` tables are code-defined (`policy.PROVIDERS`); check whether any DB constraint pins `mock` before adding a provider.
All additive; the normal Alembic path only, never `create_all` on a live database.

## 14. Testing strategy
A. Deterministic tests against a recording fake provider and a local fake webhook sender (signature, replay, duplicate, out-of-order, outage, wrong secret, tampered body); isolated database; no network.
B. Provider sandbox tests: separate owner authorization, sandbox account and sandbox credentials only, no real card (provider test cards only), webhook delivery to a controlled tunnel or a replay tool.
C. Operator-approved live readiness validation: configuration and webhook verification only, zero charges.
D. Production release approval after security qualification, owner sign-off, legal documents published and a rollback plan.
No real-money test is authorised.

## 15. Risks
Tax and legal misconfiguration; selling before commercial terms exist (the mirror treats "no terms" as unconfigured, which is the right default); entitlement drift if the translation step is unclear; webhook outage causing stale access state; provider account approval delay or product-policy rejection (Paddle); lock-in to a merchant-of-record model; fee impact on a 19.99 EUR price; privacy documents out of date; the cached-client restart behaviour for credential rotation (W12.4F); an unfinished research-cache evaluator isolation fix before integrated requalification.

## 16. Owner decisions required
**Commercial:** which provider (section 8); price, billing interval(s) and currency policy; trial; cancellation and upgrade/downgrade rules; refund policy; grace period after a failed payment and what happens to access; countries to sell to; B2C only or also business customers and invoices.
**Legal and tax:** the seller entity and its VAT position (and whether a merchant of record is wanted); statutory withdrawal and cancellation text for EU consumers; billing terms; privacy documentation updates for payment data processors; who approves the provider's seller/product review.
**Operational setup the owner must complete (not before approval):** create the provider account (sandbox first), complete seller verification, create the product and price objects, obtain sandbox credentials and the webhook signing secret and enter them only through Admin, and nominate who may approve refunds.
**Required credentials (names finalised later):** API key, webhook signing secret (and a public client token where the provider uses one). **Non-secret configuration:** provider selector, environment (sandbox or live), return/cancel URLs from the trusted application origin, price/product identifiers.

## 17. Programme state
W12.4A COMPLETE; W12.4B COMPLETE; W12.4C ENGINEERING COMPLETE (live Brevo validation deferred, tracked); **W12.4D ASSESSMENT COMPLETE, awaiting owner provider selection**; W12.4E, W12.4F, W12.5 not started; RC-P10-004 not created; AC-24 partial; P10C not started.
