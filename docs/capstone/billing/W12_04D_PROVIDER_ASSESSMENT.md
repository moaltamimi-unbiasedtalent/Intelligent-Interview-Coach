# W12.4D Phase A - Live billing provider: architecture audit and provider selection

**Status: PROVIDER SELECTED - STRIPE MANAGED PAYMENTS (primary), PADDLE (fallback). Owner-selected technical direction, subject to provider account and product eligibility.** Sections 0A to 0H below are the selection addendum (this supersedes the recommendation in section 8, which is kept as the historical first assessment). This phase is documentation only. No provider code, account, credential, checkout, subscription, refund or webhook registration was created or contacted, and no payment of any kind was initiated.

Starting point: `main` at `719fa9eacd772421cfe03b5120f39ac23b65930d` (W12.4C merged as PR #155), clean tree, Alembic head `0027_email_attempts`. W12.4A, W12.4B and W12.4C are present on main. Branch: `feat/w12-04d-billing-provider-assessment`.

Research note: provider facts below were taken from the providers' own pages during this phase (linked in section 6). Marketing pages are vendor claims, several pages did not state exact current terms, and fee figures and country lists change. Every number is labelled with its uncertainty and **must be re-confirmed on the provider's live page before the owner commits**.

## 0A. Selection addendum (owner decision recorded)
- **PRIMARY:** Stripe Managed Payments. **FALLBACK:** Paddle. **Selection status:** owner-selected technical direction for development; it is **not** authorization for live financial transactions and it depends on Stripe's eligibility review of the Ask4Mo account and product (section 0E).
- **Why the decision changed.** The first assessment compared ordinary Stripe Billing (a payment processor, where the merchant keeps VAT registration and filing) against Paddle (a merchant of record), and scored Paddle 83.0 to Stripe 82.0 with a stated flip under a small weight change. It treated Stripe's merchant-of-record product as an unconfirmed side note. The new evidence closes exactly that gap, so **the 83 versus 82 score is no longer decisive**: the like-for-like comparison is now Stripe Managed Payments versus Paddle, both merchants of record.
- **Historical record preserved.** Sections 1 to 17 below are unchanged analysis; section 7's scores describe "Stripe" as ordinary Stripe Billing + Stripe Tax and must be read that way.

## 0B. Confirmed evidence (official sources fetched for this addendum)
| Fact | Evidence | Source |
|---|---|---|
| Managed Payments is generally available | Stripe's newsroom item dated 30 June 2026 says it is now generally available, Stripe acts as merchant of record, handles local tax and regulatory compliance and payment infrastructure, and it helps German companies reach 195 markets. **The newsroom item itself does not mention SaaS subscriptions**; SaaS and subscriptions are stated on the product page and in the docs below | [Stripe newsroom](https://stripe.com/newsroom/news/stripe-tour-berlin-2026) |
| Germany is a supported seller location | Managed Payments docs list DE among the supported business locations (North America 2, Europe 33 including DE, Asia-Pacific 4) | [Eligibility](https://docs.stripe.com/payments/managed-payments/eligibility) |
| SaaS and AI services are eligible product types | Eligible digital categories include software and SaaS; approved tax codes include SaaS (personal and business use), "Artificial Intelligence as a Service - cloud based" (personal and business use), self-study web-based training and on-demand online courses | Eligibility (tax-code table) |
| Not eligible | physical goods, professional services (consulting, marketing, design, development, technical support) and live or in-person events; **a product that involves human intervention such as live 1:1 coaching is not a supported digital product** | Eligibility |
| Account conditions | an eligibility review (business type and region); direct integrations only (no Connect platforms, Express or platform-controlled accounts); you sell directly (not via a platform or marketplace); you hold the rights to the product; a low long-term dispute rate and no prior risk issues are required to stay eligible | Eligibility |
| Stripe's role | merchant of record: calculates, collects, files and remits indirect tax in 80+ countries (some jurisdictions excluded, where the seller stays responsible); fraud prevention; dispute handling including evidence submission; receipts and invoices sent by Link; customer order and subscription management in Link; transaction-level support | [How it works](https://docs.stripe.com/payments/managed-payments/how-it-works), [Managed Payments](https://stripe.com/managed-payments) |
| Integration | Stripe Checkout or Payment Links, with Billing for subscriptions; enabled per Checkout session with a `managed_payments` parameter (subscription mode shown) | Managed Payments page, how it works |
| Payment methods | cards, Apple Pay, Google Pay, Link (global, recurring supported); local methods listed are US, Korea, India, Brazil and Belgium (Bancontact, one-time only). **No SEPA Direct Debit, iDEAL or PayPal is listed** | How it works |
| Refunds and disputes | the seller can refund and update subscriptions in the Dashboard or API; refunds include the tax paid; Stripe may itself refund within 60 days in some cases and may refund without consent if the seller does not answer a product-specific support request within 48 hours; a dispute fee applies; Stripe may enable dispute-prevention tools at the seller's cost | How it works |
| Customer-facing behaviour | the customer sees **Link as merchant of record** ("Sold through Link"), statement descriptor `LINK.COM* ...`, adaptive pricing on by default (customers can pay in local currency), **custom domains are not supported at checkout**, receipts and subscription emails are Link's (the seller's receipt settings do not apply); customers manage or cancel subscriptions and payment methods in their Link account | How it works |
| Data subject deletion | a customer's deletion request through Link cancels their Managed Payments subscriptions and **deletes their data from Stripe objects, including objects in the seller's account** (customer, payment method, invoice, payment intent, subscription, charge) | How it works |
| Restricted customer countries | Ascension Island, China, Cuba, Iran, Kosovo, North Korea, Russia, Syria, Tristan da Cunha | Eligibility |
| API limitation | for subscriptions created through Managed Payments Checkout, `subscription.default_payment_method` cannot be updated directly through the API (customers use the customer portal) | How it works |
| Pricing (Germany page) | 3.5% per successful Managed Payments transaction, **on top of** payment processing fees; covers indirect tax in 75+ countries, fraud, disputes, invoicing and support; standard EEA cards 1.5% + EUR 0.25 (premium 2.8% + 0.25), international cards 3.15% + 0.25 (+2% if currency conversion); Billing pay-as-you-go 0.7%; dispute fee EUR 20. The page does not say whether Billing fees stack with the 3.5%, whether the 3.5% applies to the tax-inclusive amount, or whether the fee is returned on refund | [Stripe pricing (DE)](https://stripe.com/de/pricing), [Managed Payments pricing](https://support.stripe.com/questions/managed-payments-pricing) |

## 0C. Updated provider comparison: Stripe Managed Payments versus Paddle
| Topic | Stripe Managed Payments | Paddle |
|---|---|---|
| Germany seller eligibility | DE listed among supported business locations; subject to an eligibility review | a German business is not on the unsupported-seller list; seller account verification applies (details not on the fetched page) |
| SaaS subscription eligibility | explicit (SaaS, AIaaS, self-study training tax codes); fully automated products only | software businesses supported; the acceptable-use policy needs confirmation (section 0D) |
| MoR responsibilities | indirect tax calculation, collection, filing and remittance in 80+ countries (not everywhere), fraud, disputes, receipts and invoices, transaction support | tax in 200+ markets, invoicing as seller of record, fraud, chargebacks, buyer support |
| International coverage | customers in 195+ countries and territories except the restricted list (includes Russia and China) | 200+ countries and territories with sanctioned markets blocked; 30 currencies; payouts in USD, EUR, GBP, AUD, CAD |
| Checkout | Stripe Checkout (hosted), Link, adaptive pricing; no custom domain | Paddle checkout (overlay or inline) |
| Subscriptions and portal | Stripe Billing plus Link account for customers; optional own customer portal | built-in subscriptions and customer portal |
| Payment methods for German buyers | cards and wallets; **no SEPA or PayPal listed** | cards, PayPal and wallets (per earlier research) |
| Disputes, refunds | Stripe handles disputes (dispute fee); seller can refund; Stripe may refund within 60 days or after 48 hours without a seller reply | Paddle handles chargebacks and buyer support under its terms |
| Invoices | sent by Link; PDF attached | issued by Paddle as seller |
| API and SDK maturity | most mature ecosystem; signed webhooks and a test mode (the Managed Payments test-mode behaviour was **not confirmed** in the fetched pages) | good SDKs and a separate sandbox |
| Product approval | Managed Payments eligibility review (business type and region) on top of ordinary Stripe underwriting; Stripe's general prohibited and restricted business lists were **not reviewed in this phase** | seller verification and product review under the acceptable-use policy |
| Customer-visible seller | Link ("Sold through Link"), `LINK.COM*` | Paddle |

**Estimated cost on a EUR 19.99 charge (illustration only, not a quote).** Stripe: 3.5% (0.70) + EEA card 1.5% + 0.25 (0.55) = about EUR 1.25 (6.3%), plus Billing 0.7% (0.14) if it applies, so about 1.39 (7.0%); with an international card 3.15% + 0.25 the total is about EUR 1.58 to 1.72 (7.9% to 8.6%). Paddle: 5% + EUR 0.50 = EUR 1.50 (7.5%) all-inclusive (vendor page). **The two are within a percentage point of each other, so fees do not separate them**; the open fee questions above must be answered by Stripe before relying on any number.

## 0D. Paddle acceptable-use relevance to Ask4Mo (not a finding of violation)
Paddle's acceptable-use summary (last updated 13 April 2026) lists "automated decision-making or categorization of people" as a sub-point under the prohibited category **"Content generation"** (next to deepfakes, face swaps and voice impersonation). It gives no definition or examples, says the list is not exhaustive, and describes no confirmation process. It does not say that AI products in general are prohibited.
Ask4Mo's relevant behaviour: a candidate practises interviews and receives rubric-based feedback and a readiness score on their **own** answers; the product states these are practice feedback and not a hiring decision, stores no protected characteristics and makes no personality or health diagnosis, and no third party is evaluated or ranked. On that description it does not obviously fall under the cited sub-point, but the wording is undefined, so **this must not be assumed in either direction: Ask4Mo is not claimed to be prohibited, and permission is not claimed.** Because it is the fallback provider, a written Paddle confirmation is needed only if the fallback is ever activated.
Stripe equivalent: the fetched Managed Payments page states fully automated digital products are required and AIaaS is an eligible category, with no comparable people-categorization wording; Stripe's general prohibited and restricted businesses list and the eligibility review still apply and were not read here.

## 0E. Provider eligibility dependencies (all must be cleared by the owner before live use)
1. Stripe account in the owner's German business entity, with Managed Payments access confirmed after its eligibility review (business type and region); the account must be a direct integration (no Connect).
2. Confirmation that Ask4Mo's product maps to an eligible tax code (SaaS personal-use or AI-as-a-service personal-use, and a business-use code if B2B is sold) and counts as a **fully automated** product: Ask4Mo has no live human coaching, and any future human-in-the-loop feature would need re-checking.
3. Stripe's general prohibited and restricted businesses list reviewed against the product description (not done in this phase).
4. Acceptance that the customer sees **Link** as the seller, receives Link's receipts and subscription emails, and that checkout cannot use a custom domain.
5. A decision on payment methods: no SEPA Direct Debit, iDEAL or PayPal is listed for Managed Payments, which matters for German consumers.
6. Understanding that Stripe may refund within 60 days or after 48 hours without a seller reply, and that a customer's deletion request through Link cancels subscriptions and deletes data from Stripe objects in Ask4Mo's account.
7. A low dispute rate is a continuing eligibility condition.
8. Country policy for the restricted customer list (including Russia, although Russian is a supported interface language).
9. Fee clarification from Stripe: whether Billing fees stack with the 3.5%, the fee base (tax-inclusive or not), and fee treatment on refunds.
10. Test-mode behaviour for Managed Payments (sandbox availability and webhook parity) confirmed before W12.4D-B relies on it.
The fallback (Paddle) has its own dependencies: seller verification, product review and the acceptable-use confirmation in section 0D.

## 0F. Commercial model: decisions that stay OPEN
Premium subscription price; annual price; trial periods; cancellation rules; refund policy; grace period after a failed payment; supported countries; B2B billing; tax-inclusive versus tax-exclusive display. The **EUR 19.99 shown on the frontend is a preview, not an approved live price**, and it is not and must not be seeded as an approved commercial term (`billing_commercial_terms` stays empty, so every plan stays UNCONFIGURED). Managed Payments adds two commercial facts the owner must weigh: adaptive pricing shows local currencies by default, and the buyer sees the tax-inclusive amount Stripe calculates, so the display policy and the EUR price object need an explicit decision.

## 0G. Accepted architecture (unchanged by this selection)
Preserved: the `BillingProvider` abstraction (extended minimally in W12.4D-B), the existing billing domain and `billing_*` tables, event ingest idempotent on `(provider, provider_event_id)`, the two-person price-change and refund approvals, the 43 Admin permissions, the candidate entitlement boundary (billing is never an authorization source) and the mock provider (kept for tests and development). **No billing code is added in this branch.** Stripe-specific implications recorded for W12.4D-B to D: Checkout Sessions created server-side with Managed Payments enabled in subscription mode; Link-managed receipts mean Ask4Mo's own invoice pages are unnecessary; refund and subscription changes remain available to the seller through the API and flow through the existing dual-control refund job; **provider-initiated refunds, Stripe-initiated dispute outcomes and customer data deletion cancel subscriptions without an Ask4Mo action, so the event model must gain refund, dispute and cancellation events and the entitlement bridge must treat them as proposals**; webhooks use Stripe's signed events (raw body, timestamp tolerance, idempotency, ordering guard) as designed in section 10; credentials (API key and webhook signing secret) through the W12.4B store.

## 0H. Updated roadmap and release dependencies
- **Approved next wave: W12.4D-B Stripe Managed Payments Foundation** (adapter behind `BillingProvider`, SecretStore slots, sandbox-only mode resolution, readiness in Admin, a recording fake Stripe for tests, no checkout). Then C (Checkout and subscription lifecycle), D (signed webhooks, ordering, reconciliation and the entitlement bridge), E (customer and Billing Admin operations, refund/dispute/cancellation events), F (security qualification and sandbox acceptance). Ordering of the first wave is unchanged from section 12; only the provider and the new dependencies above change.
- **Release dependencies that stay visible:** W12.4C live Brevo delivery validation is deferred by the owner and remains a tracked release dependency (account email verification and recovery cannot be called production-ready without it); the research-cache evaluator isolation follow-up must be done before integrated requalification; W12.4F cached-provider restart handling is unchanged.

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

## 8. Original recommendation (SUPERSEDED by sections 0A to 0H; kept as history)
**The first assessment recommended Paddle** (merchant of record), with Stripe Billing as the credible alternative.**
- **Why Paddle:** Ask4Mo is a small team selling a EUR 19.99 digital subscription to a global audience. The dominant hidden cost is EU and international VAT registration, filing, invoicing and chargeback handling, which a merchant of record absorbs. Paddle also has a separate sandbox, signed webhooks and hosted checkout and portal, so the integration surface and the compliance workload are the smallest, and it fits the existing `BillingProvider` plus normalised-event design.
- **Why not Stripe (first):** the best technology, but at this scale the owner would take on VAT registration and filing (Stripe Tax Complete starts at about 80 EUR/month, or Managed Payments whose German availability is unconfirmed) and a larger integration surface. Choose Stripe if lower fees and full control matter more than outsourcing tax.
- **Why not Mollie:** it would require building the customer portal, plan changes, dunning and the entire tax and invoicing responsibility, and its subscription webhook story is weaker.
- **What it costs in trade-off:** higher percentage fee; Paddle is the seller of record, so it owns the customer invoice and the payment relationship (data minimisation benefit, but less control and branding); refunds, disputes and tax invoices follow Paddle's rules; payouts are in USD, EUR, GBP, AUD or CAD; Paddle approves sellers and products, which must be checked against Ask4Mo's AI-coaching offering and policies.

**Superseded:** the owner selected Stripe Managed Payments after updated evidence (section 0A). Nothing provider-specific is implemented in this branch.

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
| W12.4D-B (Stripe Managed Payments Foundation) | Provider adapter, SecretStore slots, mode resolution (`BILLING_PROVIDER` gains the approved provider; the mock guard stays), sandbox-only configuration, readiness in Admin | no checkout yet; extends `BillingProvider` with the minimum new methods; tests with a recording fake provider |
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
W12.4A COMPLETE; W12.4B COMPLETE; W12.4C ENGINEERING COMPLETE (live Brevo validation deferred, tracked release dependency); **W12.4D provider selected: Stripe Managed Payments (fallback Paddle); next wave W12.4D-B Stripe Managed Payments Foundation, implementation ready after this assessment merges**; W12.4E, W12.4F, W12.5 not started; RC-P10-004 not created; AC-24 partial; P10C not started.
