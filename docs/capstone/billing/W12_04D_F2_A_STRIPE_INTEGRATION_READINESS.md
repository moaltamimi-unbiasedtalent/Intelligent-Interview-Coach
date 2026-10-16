# W12.4D-F2-A: Stripe Managed Payments provider integration readiness

Status: **CODE QUALIFIED OFFLINE. EXTERNAL PROVIDER ACCESS DISABLED. SANDBOX CONNECTION PENDING.** This wave prepares the read-only provider-state boundary
for a later sandbox wave. It is not authorization to connect to Stripe, run a sandbox payment or activate a subscription, and it does not make billing
production-ready. No Stripe call, sandbox or live, was made. No migration.

Starting point: `main` at `36d0bf95b8d038b4d21a27d0a5b40a2beb1bec6a` (PR #162, F1R merged). Branch `feat/w12-04d-f2a-stripe-integration-readiness`.
Alembic head stays `0031_account_closure`. Permission registry stays 44. SDK `stripe` 16.0.0 (`>=16,<17`), pinned API version `2026-09-30.endive` (unchanged and
verified to equal the SDK's own current version).

## 1. Architecture assessment (before changes)

Reused, not rebuilt: `StripeStateReader` already existed behind the `ProviderStateReader` protocol; webhook receiver, durable outbox, reconciliation, ownership
guards, entitlement bridge, recovery, closure and scheduler were all in place and gated by code constants. Gaps found:

| Gap | Resolution |
| --- | --- |
| Status words were passed through unvalidated (an unknown Stripe status could reach reconciliation) | `_status()` validates against the documented sets; unknown is `ProviderStateInvalid("unsupported_status")` |
| Timestamps were coerced with `isinstance(int)`; a malformed value silently became `None` | `_timestamp()`: missing is `None`, present but malformed (bool, string, float, out of range) is invalid |
| `livemode` was `bool(...)` of anything, so a missing field read as sandbox | must be a real boolean; a live object in a sandbox read is `environment_mismatch` |
| Auth, permission, API-version, account and feature refusals were all retryable "unavailable" | new `ProviderStateConfiguration` (not retryable); reconciliation parks the event as `needs_review` with `provider_configuration_<category>` |
| No invoice, refund or dispute evidence reads | `get_invoice`, `get_refund`, `get_dispute` with typed snapshots |
| Read-only was a convention | every SDK call goes through `_invoke`, which resolves only `READ_ONLY_OPERATIONS` (`retrieve`/`list`) |
| No explicit provider-read authorization boundary | `policy.PROVIDER_READS_AUTHORIZED = False` (code constant) and `build_authorized_reader` (sandbox only, lazy client) |
| Admin readiness could not say which stage is missing | `readiness.provider_read_stages` (12 independent booleans) |
| Redirect validator accepted a non-default port on the checkout host | port now refused |

## 2. What was added

* `src/billing/policy.py`: `PROVIDER_READS_AUTHORIZED = False`, `PROVIDER_READ_ENVIRONMENTS = ("sandbox",)`.
* `src/billing/provider_state.py`: `ProviderStateConfiguration`; `InvoiceSnapshot`, `RefundSnapshot`, `DisputeSnapshot`; strict normalisers; `READ_ONLY_OPERATIONS`;
  hardened `StripeStateReader`; `build_authorized_reader`; `FakeStateReader` evidence stores. `build_runtime_reader()` is unchanged: it always returns the Null reader.
* `src/billing/reconcile.py`: `ProviderStateConfiguration` handled (needs review, nothing granted).
* `src/billing/operations.py`: `provider_read_stages`, `provider_reads`, `kill_switches.provider_reads_authorized`.
* `frontend/lib/billing/trustedRedirect.ts`: port refused (plus seven adversarial cases in `checkout-w12-4d-c.test.tsx`).
* `tests/test_billing_f2a_stripe_readiness.py`: 91 offline test cases (52 test functions).

## 3. The reader

Read-only, bounded, no retries inside (the job layer owns bounded retries; the client is built with `max_network_retries=0` and a 10 s timeout). Normalises:

* subscription: id, customer (id or expanded object), status, price, currency, interval, unit amount, `cancel_at_period_end` (only a real `True` counts), period end
  (item level, subscription-level fallback), latest invoice state, livemode;
* invoice and payment: status, amounts paid and due, currency, payment intent, subscription from `parent.subscription_details`; an open invoice is never payment evidence;
* refund and dispute: status, amount, currency, payment intent and charge;
* checkout-session association (single retrieval and list-by-subscription, ambiguity is invalid).

An unavailable, incomplete or unexpected answer is an error. A missing field is never defaulted into a paid or active state.

## 4. SDK and API-version compatibility

Pinned `stripe>=16,<17`, API `2026-09-30.endive`. The SDK's `_ApiVersion.CURRENT` equals the pin (asserted by a test). Managed Payments requires API `2025-03-31.basil`
or later (documented); the pin satisfies it. Nothing was changed. The reader uses only SDK methods already used and mocked in earlier waves (`v1.subscriptions.retrieve`,
`v1.checkout.sessions.retrieve|list`, `v1.invoices.retrieve`, `v1.invoice_payments.list`, `v1.charges.retrieve`) plus `v1.refunds.retrieve` and `v1.disputes.retrieve`.
Those two names follow the SDK's `v1.<resource>.retrieve` convention but were exercised only against fakes: **UNVERIFIED against the live SDK surface until F2-B** (a one-line
`hasattr` check against the installed client is part of the F2-B read-only validation).

## 5. Managed Payments eligibility assessment

Source: Stripe's Managed Payments documentation (eligibility, set-up), read in this wave (German-localised pages). Nothing below is a passed eligibility review.

| Item | Classification |
| --- | --- |
| Germany (`DE`) is on the supported business-locations list | CONFIRMED BY DOCUMENTATION |
| Direct integrations only (no Connect platform, Express or platform-controlled accounts) | CONFIRMED BY DOCUMENTATION (Ask4Mo is a direct integration); ACCOUNT-SPECIFIC VERIFICATION REQUIRED for the actual account type |
| Eligibility is decided by Stripe's own review of business type and region | ACCOUNT-SPECIFIC VERIFICATION REQUIRED |
| Managed Payments terms accepted in the Dashboard | ACCOUNT-SPECIFIC VERIFICATION REQUIRED (owner action) |
| Fully automated digital product (software, AI-as-a-service, online courses, electronically supplied services) | CONFIRMED BY DOCUMENTATION as a supported category |
| Ask4Mo as automated AI interview preparation SaaS | PRODUCT CLASSIFICATION DECISION REQUIRED (owner and legal; no human-assisted element may be sold under this product) |
| Live or human-assisted coaching, consulting, professional services | UNSUPPORTED by documentation; must never be sold through a Managed Payments product |
| Tax code: an approved code is mandatory per product (listed codes include general electronically supplied services, SaaS personal use and business use, AI-as-a-service cloud personal use and business use) | CONFIRMED BY DOCUMENTATION that a code from the approved list is required; **which code applies is a PRODUCT CLASSIFICATION DECISION REQUIRED. No production tax code was selected or seeded.** |
| Customer countries: more than 195 supported; restricted: Ascension, China, Cuba, Iran, Kosovo, North Korea, Russia, Syria, Tristan da Cunha | CONFIRMED BY DOCUMENTATION. Ask4Mo's sellable countries are an unapproved owner decision. Note: Russia is a restricted purchase country although Russian is an interface language (the interface locale does not imply availability). |
| Ongoing: low dispute rate, refunds possible by Stripe within 60 days, consumer-protection withdrawal periods applied by Stripe | CONFIRMED BY DOCUMENTATION; effect on Ask4Mo refund and cancellation policy is an unapproved owner decision |
| Unsupported integrations | Connect, Express and platform-controlled accounts (documented). Other Stripe features Ask4Mo does not use (Stripe Tax add-on, invoicing outside Checkout) are not planned. |
| API version | `2025-03-31.basil` or later: CONFIRMED BY DOCUMENTATION; pin satisfies it |

## 6. Provider response contracts

Each contract is enforced by the typed normalisers and by tests: expandable object or id (both accepted for customer, latest invoice, payment intent, charge, invoice, subscription);
null or missing required field (invalid, not defaulted); unexpected status (invalid); malformed timestamp or amount or currency (invalid); currency allow-list (optional, default
accepts any well-formed code because the owner has approved no currencies); live object in a sandbox read (invalid); API-version differences (see 8); id echo mismatch (invalid).

## 7. Checkout contract and redirect

Mocked-SDK tests prove: `managed_payments.enabled = true`, `mode = subscription`, one line item with the approved Price ID and quantity 1, no client-supplied amount, no
`automatic_tax` or `payment_method_types` (Managed Payments owns tax and methods), success and cancel URLs from the trusted origin, a stable idempotency key, and refusal
without authorization. The documented Checkout URL form is `https://checkout.stripe.com/c/pay/cs_...`. The redirect validator therefore stays at the single exact host
`checkout.stripe.com`, https only, no credentials, now default port only. No broader allow-list was added. **UNVERIFIED for F2-B:** whether Managed Payments sessions can return a different
host (for example a custom domain or a Link-hosted page). If the sandbox session returns another host, expand the allow-list only with the exact host and the adversarial cases already in the suite.

## 8. Webhook API-version and event compatibility

The receiver and normaliser are pinned to `2026-09-30.endive` (`SUPPORTED_API_VERSIONS`). A snapshot event with any other (or missing) `api_version` is stored with
status `ignored` and category `unsupported_api_version`, is visible in Admin, and never grants or revokes (tested for `2020-01-01`, a future version, empty and `None`).
Thin-style (v2) payloads without `data.object` are refused by `parse_event`. Required fields come from the reader, not from the event, so an event can never carry authority. No webhook
was registered. **F2-B decision:** the webhook endpoint's API version must be set to the pinned version when the endpoint is created.

## 9. Subscription ownership, closure and reconciliation

Ownership is only through the trusted checkout record. Offline end-to-end tests through the real reader (recording fake client) cover: valid grant under the synthetic policy;
replay and sibling events (one grant); unapproved runtime policy (nothing granted); scheduled cancellation (access kept, flag recorded) then provider cancellation (revoked); cross-candidate
checkout reference (nothing granted); provider outage, rate limit and API error (retry, nothing granted); credential and permission refusal (needs review, nothing granted); live object in a sandbox
world (needs review); refund and dispute through the verified pipeline. F1 and F1R suites continue to cover duplicate, stale, old-cancelled, missing mapping, environment isolation, concurrency,
recovery authorization and closure. The synthetic policy exists only in tests.

Account closure: the reader supplies states only when a future reader exists; today closure reports `provider_reader_unavailable` and never claims billing stopped.
Distinctions kept: cancellation requested, scheduled (`cancel_at_period_end`), confirmed (`canceled` fact) and effective (period end); scheduling is not billing stopped. Provider cancellation
contract for F2-B: the candidate cancels in Link (Customer Portal equivalent under Managed Payments); Ask4Mo performs **no** cancellation and **no** customer-deletion call; the reader confirms
`canceled` afterwards. Retained billing references are pseudonymised (an anonymised shell with provider ids), which is not anonymisation; retention periods remain an owner and legal decision.

## 10. Link and Customer Portal findings

Under Managed Payments, Link acts as merchant of record and supports subscription management and transaction support on link.com. Test purchases do not appear in the Link app.
No management URL is fabricated: candidate guidance remains text only. Whether a documented, stable management URL or a Customer Portal session may be offered is UNVERIFIED for F2-B.

## 11. Configuration and secrets

SecretStore slots (W12.4B, unchanged): `STRIPE_SANDBOX_SECRET_KEY`, `STRIPE_SANDBOX_WEBHOOK_SECRET` (future), plus the live slots (unusable). Non-secret config: `BILLING_PROVIDER`, `STRIPE_ENVIRONMENT`.
Nothing asks for a credential, and none is in docs, git, snapshots, logs or responses. The default factory builds a per-instance client through `build_stripe_client` (sandbox only, restricted-key-capable prefixes
`sk_test_`/`rk_test_`, no global key, no retries, bounded timeout) and surfaces configuration refusals as `ProviderStateConfiguration`.

## 12. Authorization and network gating

`PROVIDER_READS_AUTHORIZED = False` is a code constant. No setting, credential, rotation, Admin readiness view, webhook, recovery action or scheduler can change it. While False,
`build_authorized_reader` refuses; even when True it refuses live and builds no client until the first read. `build_runtime_reader()` ignores the gate and returns the Null reader, and
no application code constructs a real reader (a source scan asserts only `provider_state.py` does). Tests prove status surfaces run while every reader constructor raises. There is no generic outbound HTTP
client in `src/billing`. All tests run with non-loopback sockets blocked.

## 13. Error handling

| Provider condition | Category | Class | Retry |
| --- | --- | --- | --- |
| authentication, permission | `provider_auth_failed`, `provider_permission_denied` | Configuration | no |
| invalid API version, unsupported Managed Payments feature, wrong account | `invalid_api_version`, `unsupported_feature`, `wrong_account` | Configuration | no |
| no such resource | `not_found` | NotFound (event quarantined) | no |
| malformed or unexpected answer | `incomplete_response`, `unsupported_status`, `malformed_*`, `environment_mismatch` | Invalid (needs review) | no |
| timeout, outage, rate limit, unknown | `provider_timeout`, `provider_unavailable`, `rate_limited` | Unavailable | yes, bounded by the job layer |

No raw payload or SDK message is stored or logged.

## 14. Admin readiness

`provider_read_stages`: reader implemented, reader selected at runtime, credentials configured, sandbox authorized, eligibility verified, external reads authorized, checkout authorized,
webhook authorized, scheduler enabled, entitlement policy approved, sandbox qualification passed, production approved. Today only "reader implemented" is true (and "credentials configured" when slots hold
well-formed values). A test asserts none of "connected", "healthy" or "operational: true" appears. Admin recovery is unchanged: `platform.billing.recover` plus fresh step-up; `platform.jobs.manage` confers nothing; recovery
is refused while the reader is Null and cannot activate reads.

## 15. Financial policy boundary (unapproved owner decisions)

Monthly and annual prices, trial, grace, refund, cancellation and dispute policy, currencies, sellable countries, B2B treatment, tax-inclusive display, legal seller entity, retention. No price was seeded; EUR 19.99 stays a
preview. The runtime entitlement policy stays unapproved.

## 16. Offline qualification

See the PR and the final report for counts. Protected stores: fingerprint-checked by the suite's session guard; `scripts/eval_retrieval.py` and the cache-mutating evaluator were not run.
`eval_product_coverage` (94 % insufficient-evidence, n = 412) remains BELOW GATE and is an unresolved programme dependency, not a pass.

## 17. Unverified contracts (all deferred to F2-B)

`v1.refunds.retrieve` and `v1.disputes.retrieve` on the live SDK surface; the Checkout URL host for Managed Payments sessions; the Link or Customer Portal management URL; whether the account passes the Managed Payments
review; the exact Link-side behaviour of cancellation timing; webhook event delivery shape for Managed Payments (including `invoice.paid` ordering); whether `invoice_payments.list` is available to restricted keys.

## 18. F2-B owner checklist (nothing here was performed)

**REQUIRED FOR READ-ONLY SANDBOX VALIDATION**
1. Legal seller entity decision.
2. Stripe account onboarding by the owner; Managed Payments eligibility review submitted and outcome recorded.
3. Sandbox availability confirmed for Managed Payments.
4. A restricted sandbox API key (read scopes only: subscriptions, checkout sessions, invoices, refunds, disputes, charges) entered by the owner through the Admin SecretStore control, never in chat.
5. Written authorization to flip `PROVIDER_READS_AUTHORIZED` in a reviewed release (sandbox only).
6. Expected network operations list approved (the `READ_ONLY_OPERATIONS` table), rollback plan (flip the constant back), credential rotation procedure, failure monitoring owner.

**REQUIRED FOR SANDBOX CHECKOUT TESTS (in addition)**
7. Product classification decision and approved tax code for the test product.
8. Test product and Price IDs created in the sandbox; the approved Price ID mapping recorded via the existing Admin mapping (no price seeded by code).
9. Webhook signing secret for the sandbox endpoint entered by the owner; webhook endpoint created with the pinned API version and the 14 allow-listed event types; `STRIPE_WEBHOOK_AUTHORIZED` flip authorized.
10. `EXTERNAL_CHECKOUT_AUTHORIZED` flip authorized for sandbox; test callbacks and the sandbox isolation boundary confirmed.
11. Synthetic or sandbox-only entitlement policy approved for the test window and never in a hosted production environment.

**REQUIRED FOR PRODUCTION ACTIVATION (not before F3 and owner sign-off)**
12. All commercial policies approved (prices, trial, grace, refund, cancellation, dispute, currencies, countries, B2B, tax display) and the production entitlement policy approved.
13. Financial-data retention review complete; legal review of Terms and Privacy for billing.
14. Live account and live slots, live webhook, scheduler enablement, `LIVE_BILLING_ENABLED` change in a reviewed release, owner confirmation of each switch.

## 19. F3 acceptance plan (outline)

Sandbox purchase, renewal, failed payment, cancellation (scheduled and immediate), refund, dispute, replay and out-of-order delivery, each verified through the existing pipeline with the sandbox policy;
account-closure with a live sandbox subscription; credential rotation and outage drills; reader contract re-validation against real payloads (replace synthetic fixtures); evidence stored in `artifacts/`.

## 20. Programme dependencies still open

W12.4C live Brevo validation deferred; research-cache evaluator isolation unresolved; product coverage below gate; Managed Payments eligibility and sandbox access unverified; commercial policies and the
production entitlement policy unapproved; financial-data retention review outstanding; Admin step-up is password-based (OIDC-only accounts fail closed); W12.4E, W12.4F, W12.5 not started; RC-P10-004 not
created; AC-24 partial.
