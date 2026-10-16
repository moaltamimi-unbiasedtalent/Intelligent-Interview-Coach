# W12.4D-F2-B1: Stripe account and sandbox readiness

Status: **PREPARED. OWNER STRIPE ONBOARDING REQUIRED. NO EXTERNAL FINANCIAL OPERATIONS AUTHORIZED.**
This is a readiness and verification document. It performs no Stripe call, creates no account, product, price, key or webhook, accepts no terms and enables nothing.
Stripe is **not connected** and billing is **not operational**. No code changed in this wave (documentation only, no migration).

Documentation sources: Stripe Managed Payments pages (eligibility, set-up), read in W12.4D-F2-A and cited from that review. Statements marked "documentation" were read there;
anything Stripe may have changed since must be re-read by the owner at onboarding time. Nothing below is account-specific evidence.

## 1. Starting point and billing safety verification

* `main` = `513cfb58f78489f48cc57a9dbeed10f762ec1fb5` (PR #163, W12.4D-F2-A merged; F2-A commit `c99233f` is an ancestor). Alembic head verified: `0031_account_closure`.
* Working tree clean apart from the four unrelated untracked frontend assets (preserved). Branch `docs/w12-04d-f2b1-stripe-sandbox-onboarding`.
* Verified in `src/billing/policy.py` (code constants, unchanged): `LIVE_BILLING_ENABLED = False`, `EXTERNAL_CHECKOUT_AUTHORIZED = False`, `STRIPE_WEBHOOK_AUTHORIZED = False`,
  `RECONCILE_SCHEDULER_ENABLED = False`, `PROVIDER_READS_AUTHORIZED = False`, `PAID_ENTITLEMENT_POLICY_APPROVED = False`.
* The runtime provider-state reader is the Null reader (`build_runtime_reader()` has no code path to a real one; F2-A test enforces that only `src/billing/provider_state.py` constructs `StripeStateReader`).
* Security controls untouched: 44 Admin permissions, `platform.billing.recover` with fresh step-up, two-person financial approvals, subscription-aware closure, privacy-erasure separation,
  checkout idempotency, webhook signature verification, bridge-only entitlement writes, tenant isolation, SecretStore.

## 2. Seller eligibility requirements (owner checklist input)

| Requirement | Source | Status for Ask4Mo |
| --- | --- | --- |
| Legal seller entity (the business that owns the Stripe account) | owner | **OWNER DECISION REQUIRED**; not invented here |
| Business location on the supported list (Germany `DE` is listed) | documentation | CONFIRMED BY DOCUMENTATION for `DE`; the actual entity's location must match: ACCOUNT-SPECIFIC VERIFICATION REQUIRED |
| Direct integration (no Connect platform, Express account or platform-controlled account) | documentation | Ask4Mo is a direct integration; actual account type: ACCOUNT-SPECIFIC VERIFICATION REQUIRED |
| Business type | Stripe eligibility review | ACCOUNT-SPECIFIC VERIFICATION REQUIRED |
| Stripe account verification (identity, business, bank details) | Stripe onboarding | owner action |
| Managed Payments terms accepted in the Dashboard | documentation | owner action; **no one else may accept legal terms** |
| Managed Payments eligibility review passed | Stripe | ACCOUNT-SPECIFIC VERIFICATION REQUIRED; never assumed |
| Sandbox availability for Managed Payments | Stripe | ACCOUNT-SPECIFIC VERIFICATION REQUIRED |
| Fully automated digital product, sold directly, with all rights to distribute | documentation | see section 3 (PRODUCT CLASSIFICATION DECISION REQUIRED) |
| Approved Managed Payments tax code per product | documentation | see section 4 (OWNER APPROVAL REQUIRED) |
| Restricted customer countries (Ascension, China, Cuba, Iran, Kosovo, North Korea, Russia, Syria, Tristan da Cunha) | documentation | applies to purchasers; Russian interface language does not imply Russian availability |
| Ongoing dispute-rate and refund conditions | documentation | affects refund and dispute policy (section 6) |

## 3. Ask4Mo product description (verified against the implementation)

Verification basis: the code and CLAUDE.md as of `513cfb5`. Every claim below states whether it is IMPLEMENTED, or PLANNED and therefore not to be used in Stripe or marketing text.

**Short description (for the Stripe product and the account review):**
"Ask4Mo is an automated, AI-powered web application that helps candidates prepare for job interviews: an AI assistant (Mo) that guides role and interview preparation, and automated
mock-interview practice with written feedback. All functionality is delivered online by software; no human provides coaching, recruiting or placement."

**Detailed description:**
Candidates use Ask4Mo in a web browser. IMPLEMENTED: (1) **Prepare**, an AI agent (Mo) that analyses a role or job description the candidate supplies and builds preparation guidance grounded in a curated labour-market and
careers knowledge base with citations; (2) **Practice**, automated mock interviews where AI generates questions and evaluates the candidate's typed answers against a rubric, then produces a report (practice feedback, not a hiring decision);
(3) **Opportunities**, a private workspace for one target job; (4) **Documents and evidence**, private upload of the candidate's own documents with deterministic extraction and approval before use; (5) **Company intelligence**
built from official sources with explicit fact versus inference labelling; (6) optional browser-based voice input and playback, with no audio stored; (7) eight interface languages; (8) in-app support tickets answered by Ask4Mo staff.
Content is AI generated and can be wrong; the product states it is practice guidance.

**Subscription-service description:** Premium is a recurring monthly digital subscription to the Ask4Mo web application. **Important finding:** in the current code the Premium plan equals the Basic entitlements plus a single
`premium_preview` key (`src/entitlements.py`, `DEFAULT_PLANS`), and the pricing page labels Premium a preview with EUR 19.99 as a preview figure. What a paying subscriber receives that Basic does not is therefore **not yet defined**
(OWNER DECISION REQUIRED). The Stripe product description must not promise features that no entitlement enforces.

**Digital delivery explanation:** Access is granted electronically and immediately by the server after verified provider confirmation; there is no download, shipment, event or human service. Access ends when the verified subscription state ends.

**Customer support explanation:** Support is via in-app tickets (Admin-answered). There is no live chat, phone line or support SLA. Billing and subscription support for a Managed Payments purchase is also offered by Link (documentation: Link supports
transaction support and subscription management). The support address and response commitment are OWNER DECISIONS.

**Must not be described as:** a human recruiter, a recruitment agency, a live human coaching or consulting service, a job-placement or employment guarantee, a hiring decision tool, "bias-free", or "GDPR compliant". PLANNED or NOT IMPLEMENTED
and so excluded: Premium-specific features, annual plan, workspace billing, real-time company intelligence, Glassdoor/Kununu/Google/LinkedIn sources, realtime voice live validation.

**Refund and cancellation dependencies:** the Terms, Privacy and in-product text must match the approved refund, cancellation and withdrawal policy; Stripe may refund within 60 days and applies regional withdrawal periods (documentation). The policy text is not approved (section 6).

## 4. Tax-code review (OWNER APPROVAL REQUIRED; nothing selected or seeded)

Candidate codes from Stripe's approved Managed Payments list (documentation), assessed against the actual product (cloud-hosted AI tools accessed in a browser, no download, individual candidates):

| Code | Category | Fit |
| --- | --- | --- |
| `txcd_10105001` | AI as a service, cloud based, personal use ("access to AI tools such as LLMs or chatbots hosted entirely on the provider's servers and accessed via a web browser; personal use") | **Best textual fit for the candidate-facing Premium subscription.** Ask4Mo is hosted entirely server side, used via a browser, built on LLMs, bought by individuals for personal career use. |
| `txcd_10105002` | AI as a service, cloud based, business use | Applies only if Premium is sold to organisations or for employer use. B2B is an undecided owner item. Not recommended for the individual plan. |
| `txcd_10103000` | SaaS, personal use | Reasonable fallback: browser software not customised for a buyer. Less specific because the value is AI generation. |
| `txcd_10103001` | SaaS, business use | Same as above for business buyers. |

Recommendation: `txcd_10105001` for an individual Premium plan, **subject to the owner's and tax adviser's confirmation**; use the business variant only if a B2B plan is approved. The personal/business distinction matters only for US sales per the documentation.
Whether Stripe's classification of Ask4Mo agrees is ACCOUNT-SPECIFIC VERIFICATION REQUIRED. **OWNER APPROVAL REQUIRED. No tax code is approved.**

## 5. Owner decision register

Nothing here is approved. "Needed for" is the earliest stage that cannot proceed without it. B1 = account readiness, B2 = read-only sandbox connection, F3 = sandbox subscription transactions, PROD = commercial activation.

| Decision | Status | Needed for |
| --- | --- | --- |
| Legal seller entity | OPEN | B1 |
| Product classification (automated digital product, no human-assisted element sold) | OPEN | B1 |
| Product tax code | OPEN (recommendation in section 4) | B1 for the test product |
| What Premium includes beyond Basic | OPEN (finding in section 3) | F3 (test product copy), PROD |
| Premium monthly price | OPEN | F3 (sandbox test price), PROD (real price) |
| Premium annual price | OPEN (no annual plan exists) | PROD |
| Currency | OPEN | F3, PROD |
| Tax-inclusive presentation | OPEN | F3 (`tax_behavior`), PROD |
| Supported customer countries | OPEN | PROD (checkout geography), copy before F3 |
| B2B subscriptions | OPEN | PROD (also affects tax code) |
| Trial policy | OPEN | F3 (trial scenarios), PROD |
| Failed-payment grace period | OPEN | F3, PROD |
| Cancellation policy | OPEN | F3, PROD |
| Refund policy | OPEN | F3, PROD |
| Dispute entitlement policy | OPEN | F3, PROD |
| Billing data retention | OPEN (owner and legal) | PROD (and before storing real financial data) |
| Authorization to flip `PROVIDER_READS_AUTHORIZED` (sandbox) | NOT GRANTED | B2 |
| Authorization for sandbox checkout and webhook switches | NOT GRANTED | F3 |
| Sandbox entitlement policy for the test window | NOT GRANTED | F3 |

B1 needs only the first three. B2 additionally needs the read-gate authorization. Prices and policies are not needed to read a sandbox; they are needed before any sandbox transaction.

## 6. Stripe Dashboard onboarding checklist (owner performs; nothing performed here)

1. Decide and record the legal seller entity.
2. Create or select the Stripe account for that entity and complete account verification.
3. Confirm the account is a direct (non-Connect) account.
4. Open Settings, Managed Payments; read and, if the owner agrees, accept the Managed Payments terms **personally**.
5. Confirm Managed Payments is available (eligibility outcome) and whether it is available in the sandbox.
6. Record the eligibility outcome and any conditions in the decision register (a screenshot is not to be committed if it shows account identifiers).
7. Decide product classification and tax code (section 4).
8. In the sandbox only, and only after the F3 decisions exist: product and price creation (not in B1 or B2).
9. Create the restricted sandbox key (section 8) and enter it in the Admin SecretStore control; never paste it in chat, a ticket, a document or git.

## 7. Sandbox environment design

* **Isolation:** one sandbox of the owner's Stripe account; the live environment is never configured. Sandbox keys are `sk_test_`/`rk_test_`; a live-looking value in the sandbox slot is refused by `build_stripe_client`
  (`credential_environment_mismatch`). `STRIPE_ENVIRONMENT` defaults to sandbox, an unknown value fails closed, and the reader refuses `live` at construction.
* **Credentials:** four separate SecretStore slots; only `STRIPE_SANDBOX_SECRET_KEY` is needed for B2; `STRIPE_SANDBOX_WEBHOOK_SECRET` only for F3.
* **Identity validation (B2 acceptance step):** the first read must also prove the key belongs to the intended sandbox account. A read-only, no-side-effect account/identity read is not part of the current `READ_ONLY_OPERATIONS`
  table; adding one (for example retrieving the account) is a reviewed code change in B2 and must go through the same table. Until then the identity check is by the owner comparing the account in the Dashboard with the key's account.
* **Read-only testing:** `READ_ONLY_OPERATIONS` (`retrieve`/`list` only). Reads are single attempts, 10 s timeout, no retries in the client.
* **Safe logging:** categories only; no raw payloads, no SDK messages, no keys; response ids masked in Admin.
* **Rollback:** (1) set `PROVIDER_READS_AUTHORIZED` back to False in a reviewed release (code constant, immediate on deploy); (2) remove the sandbox key through the Admin SecretStore control (step-up, audited);
  (3) the Null reader is the default so nothing else is needed; (4) in-flight events are durable and re-processable after recovery.

## 8. SecretStore requirements and API permissions

* Slots (exist): `STRIPE_SANDBOX_SECRET_KEY` (B2), `STRIPE_SANDBOX_WEBHOOK_SECRET` (F3). Backend `SECRET_STORE_BACKEND=encrypted_database` with a deployment-managed `SECRET_STORE_MASTER_KEY` is required to enter them through Admin
  (otherwise the environment adapter is read-only and the owner sets deployment variables). Configure, replace and remove need `platform.integrations.secret.rotate` (platform admin) and a fresh password step-up. Rotation takes effect without a restart for the reader because the client is built per read.
* **Restricted key (read-only), proposed scopes to confirm in the Dashboard UI at creation:** Subscriptions: read; Checkout Sessions: read; Invoices: read; Charges (and PaymentIntents if required): read; Refunds: read; Disputes: read;
  Customers: none unless a read proves necessary. No write scope of any kind. The exact permission names are Stripe UI strings and **must be confirmed by the owner at creation**; if `invoice_payments.list` is not available to restricted keys,
  that finding is recorded and either the scope is widened to read or the call is replaced in a reviewed change.
* Account identifier handling: the Stripe account id is an internal identifier and is not secret, but is not committed to git.

## 9. Webhook compatibility assessment

Findings from the code (`ProviderEventService.accept`, `src/billing/operations.py`), for a **validly signed** event whose `api_version` differs from the pinned `2026-09-30.endive`:

| Question | Finding |
| --- | --- |
| Durably recorded? | YES. A row is stored with status `ignored` and category `unsupported_api_version`, plus the `billing.webhook_event_ignored` audit event. |
| Visible to administrators? | PARTLY. Visible in the event list (filter `ignored`) and the event detail ("Ignored by design"); counted as `ignored` in the overview. It is NOT included in `awaiting_operator` or in the reconciliation attention list. |
| Actionable alert? | NO. There is no alert, no distinct counter and no readiness warning for this category. |
| Eligible for reconciliation? | NO. `processed_at` is set at acceptance, the event is not recoverable (`recoverable` only for failed, needs review, quarantined), and `normalized_json` is empty. |
| Can it change entitlements directly? | NO. Entitlements change only through the bridge after an authoritative provider read; an ignored event runs nothing. |

**Integrity assessment:** there is no grant or revocation integrity gap in the unsafe direction (no unverified grant, no unverified revocation). There **is a bounded liveness gap**: if a webhook endpoint were created with a different API
version than the pin, every meaningful financial event (payment, cancellation, refund, dispute) would be silently stored as `ignored`, and with the scheduler disabled nothing would trigger re-reading the provider, so a cancellation or refund
could leave a stale paid entitlement until an operator reconciles a link by hand. This is a configuration-time risk (the endpoint API version is chosen by the owner) with no alert.

**Bounded remediation (documented only, to be implemented and tested in B2 or a dedicated small wave before any webhook is registered; not done here; webhooks stay disabled):**
1. Overview and reconciliation views count `ignored:unsupported_api_version` events for SUPPORTED event types separately and include them in `awaiting_operator`; the readiness block shows a warning while any exist.
2. For a supported event type with an unsupported version, record the event as `needs_review` with the object id taken only from `data.object.id` (no other field trusted), so an operator can run the existing "reconcile one link" recovery, which reads authoritative state and never trusts the event.
3. Procedure: create the endpoint with the pinned API version (owner checklist), and treat any such event after go-live as a configuration incident.
No broadening of the integration and no new entitlement path.

## 10. Financial event recovery assessment

Recovery today: events in `failed`, `needs_review` or `quarantined` can be retried by an administrator holding `platform.billing.recover` with fresh step-up (bounded operator retries, idempotency key, audited), and a link can be reconciled on demand; both
are refused while the reader is Null. Expired leases are requeued. An authoritative read replaces event content, so a lost or duplicated event cannot corrupt state. Gaps: `ignored` events are not recoverable (section 9), the scheduler that would re-read stale links is
disabled, and there is no alert on events awaiting an operator beyond the overview counts. Enabling the scheduler is a separate owner-authorized step after the sandbox qualification.

## 11. Sandbox API contract test plan

Status vocabulary: DOCUMENTED = in Stripe docs reviewed; OFFLINE TESTED = covered by F2-A fake-client tests; SANDBOX VALIDATION REQUIRED; ACCOUNT-SPECIFIC VALIDATION REQUIRED; UNSUPPORTED.

| Contract | Documented | Offline tested | Sandbox validation | Account-specific | Notes |
| --- | --- | --- | --- | --- | --- |
| Subscription retrieval (status, items, period end, cancel flag) | yes | yes | REQUIRED | | confirm `current_period_end` is item-level in this API version |
| Invoice and payment evidence (`invoices.retrieve`, parent subscription) | yes | yes | REQUIRED | | |
| Invoice payment listing (`invoice_payments.list`) | yes (basil or later) | yes | REQUIRED | restricted-key access | |
| Refund retrieval (`refunds.retrieve`) | yes | yes (fakes) | REQUIRED | | SDK method path unverified against the live client |
| Dispute retrieval (`disputes.retrieve`) | yes | yes (fakes) | REQUIRED | | SDK method path unverified |
| Checkout Session response (id, url, expiry) | yes | yes | REQUIRED (F3) | Managed Payments availability | |
| Checkout redirect URL host | documented example `checkout.stripe.com` | yes (strict) | REQUIRED (F3) | | expand only to the exact observed host |
| Webhook event API version | yes | yes (ignored path) | REQUIRED (F3) | | see section 9 |
| Link customer management (cancel, manage) | yes (Link site) | n/a | REQUIRED (F3) | live-mode only for Link app visibility | test purchases do not appear in the Link app |
| Subscription cancellation | yes | yes (facts) | REQUIRED (F3) | | Ask4Mo performs none |
| Account closure with active billing | n/a | yes | REQUIRED (F3) | | |
| Managed Payments for non-eligible products | yes | n/a | n/a | | UNSUPPORTED (human-assisted, physical, events) |
| Connect, Express, platform-controlled accounts | yes | n/a | n/a | | UNSUPPORTED |

## 12. Staged test plan (each stage needs its own owner authorization; no live payments in any stage)

**Stage A, read-only (B2).** Precondition: B1 complete, restricted sandbox key stored, `PROVIDER_READS_AUTHORIZED` flipped in a reviewed release for sandbox. Steps: confirm authentication (a retrieve of a non-existent id must return `not_found`, proving
the key works without creating anything); confirm sandbox isolation (a `livemode` true object is refused); enumerate that every `READ_ONLY_OPERATIONS` resource exists on the live client (`hasattr` checks including `refunds` and `disputes`); validate the response
contracts for any resources that already exist in the sandbox (none are created by Ask4Mo in this stage); confirm the error categories for a bad key and for a wrong id. No writes, no webhooks, no checkout.

**Stage B, controlled sandbox integration (F3 part 1).** Only after separate authorization: owner creates the sandbox product and price (approved tax code); the price is mapped through the existing Admin price mapping; `EXTERNAL_CHECKOUT_AUTHORIZED` flipped for sandbox;
validate session creation with `managed_payments.enabled=true`, the returned hosted URL host, expiry margin and idempotent replay; register the sandbox webhook endpoint with the pinned API version and the 14 allow-listed events, `STRIPE_WEBHOOK_AUTHORIZED` flipped for sandbox;
validate signature verification, durable storage and ownership against a Checkout started by a test candidate.

**Stage C, subscription acceptance (F3 part 2).** Only after separate authorization and an approved sandbox entitlement policy: test-card purchase; renewal (test clocks); payment failure and recovery; scheduled and immediate cancellation (through Link, not Ask4Mo);
refund (initiated in the Stripe Dashboard by the owner); dispute (Stripe test dispute); entitlement transitions per the sandbox policy; out-of-order and replayed events; account closure with an active sandbox subscription; credential rotation and an induced outage.

## 13. Account-closure validation

Offline: closure case recorded, no provider call, deletion refused while a subscription is unresolved, retained erasure keeps a pseudonymised billing shell (F1R tests). Sandbox (F3): the candidate cancels in Link; the reader confirms `canceled`; closure completes;
scheduling a cancellation is verified to be distinct from billing stopped. Ask4Mo never cancels, never deletes a Stripe customer, and retention periods remain unapproved.

## 14. Link management limitations

Under Managed Payments Link is the merchant of record and hosts subscription management and transaction support. Test-mode purchases do not appear in the Link app (documented), so cancellation through Link can be exercised only in live mode, which this programme does not
authorize. Consequence: **candidate-initiated cancellation through Link cannot be fully validated in the sandbox**; sandbox cancellation is limited to what Stripe exposes for test subscriptions (for example Dashboard-side cancellation by the owner), and the Link flow remains
ACCOUNT-SPECIFIC and PRODUCTION-STAGE VALIDATION REQUIRED. No management URL is fabricated; candidate guidance stays text.

## 15. Security safeguards (unchanged)

44 permissions; `platform.billing.recover` plus fresh step-up (jobs-manage confers nothing); two-person approvals for price change and refund; subscription-aware closure; privacy-erasure separation; checkout idempotency; signature verification (raw body, tolerance both directions,
environment and API-version checks); bridge-only entitlement writes under an owner-approved policy; tenant isolation; SecretStore (no value readable by any route). Additional B2 rule: any code that adds an operation extends `READ_ONLY_OPERATIONS` only, with a test.

## 16. Owner authorization boundaries

NOT authorized by this document or this wave: Stripe account creation or login, accepting Stripe terms, live or sandbox API calls, product and price creation, Checkout Session creation, webhook registration, test transactions, refunds, subscription changes, customer deletion, scheduler enablement,
changing any activation constant, production entitlements. Each stage in section 12 requires a separate, explicit, written owner authorization naming the stage, the environment (sandbox) and the constants to flip.

## 17. Exact prerequisites for F2-B2 (read-only sandbox connection)

1. B1 outputs recorded by the owner: legal seller entity, Managed Payments eligibility outcome, sandbox availability, product classification.
2. Restricted read-only sandbox key created by the owner and stored through the Admin SecretStore (encrypted-database backend configured, master key provisioned by the deployment).
3. Written authorization to flip `PROVIDER_READS_AUTHORIZED` for sandbox in a reviewed release, with rollback owner and failure-monitoring owner named.
4. Approval of the `READ_ONLY_OPERATIONS` network operation list (section 7) and of the identity-validation read.
5. Decision on the webhook-version remediation (section 9): it may ship with B2, but must precede any webhook registration.
6. An isolated sandbox environment for the API deployment (no production database, no real candidates) and a decision where B2 evidence is stored.
F2-B2 must not start before 1 to 4 are confirmed; it must not create products, prices, checkout sessions or webhooks.

## 18. Programme dependencies still open

W12.4C live Brevo validation deferred; research-cache evaluator isolation unresolved; product coverage (insufficient-evidence 94 %, n = 412) below gate; Managed Payments eligibility and sandbox access unverified; commercial policies and the production entitlement policy unapproved;
financial-data retention review outstanding; Admin step-up is password based (OIDC-only accounts fail closed); W12.4E, W12.4F, W12.5 not started; RC-P10-004 not created; AC-24 partial.
