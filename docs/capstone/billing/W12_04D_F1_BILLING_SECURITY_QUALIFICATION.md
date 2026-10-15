# W12.4D-F1 - Billing security and architecture qualification

**Status: CODE QUALIFIED (deterministic, offline) - BILLING SECURITY AND ARCHITECTURE VERIFIED OFFLINE - STRIPE SANDBOX INTEGRATION PENDING.** An independent audit of the whole billing implementation against the repository (not against earlier wave summaries). It found **no Critical** and **one High** finding (an activation gate, not exploitable today), corrected nine bounded defects with regression tests, and left every provider-dependent assumption marked **PROVIDER VALIDATION REQUIRED**. No Stripe call of any kind (not even sandbox) was made, no account was touched, no kill switch was changed, no policy was approved and no price was seeded. Billing is **not production-ready**; W12.4D is **not** complete (F2 and F3 remain).

Starting point: `main` at `b3a2b261c4fc2e394bb84ad91870a5a359e38a27` (W12.4D-E merged as PR #160), Alembic head `0030_billing_recovery`, clean tree apart from the four unrelated untracked frontend assets. Branch `feat/w12-04d-f1-billing-security-qualification`. **No migration was added.**

## 1. Executive assessment
The architecture holds its central invariants under adversarial test: nothing untrusted becomes financial or entitlement state without passing signature verification, environment validation, durable acceptance, a provider-state read, ownership and price verification and an explicit entitlement policy; the entitlement bridge is the sole writer of provider-managed grants and is only reachable from reconciliation; all five kill switches are code constants that no configuration, credential, Admin action or price mapping can flip. The audit found real defects at the edges (concurrency classification, a checkout expiry boundary, deletion on non-FK databases, audit growth, key-collision handling, misleading copy) and one genuinely significant open issue that needs an owner and legal decision before any live subscription can exist (section 6, F1-07).

## 2. Architecture inventory (status per component, from the code)
| Component | Status |
|---|---|
| `BillingProvider` protocol, `MockBillingAdapter` | IMPLEMENTED, TESTED, MOCK ONLY (events and mirrors pinned to `mock`) |
| `StripeManagedPaymentsProvider` (checkout, refund refusal) | IMPLEMENTED, TESTED, DISABLED (capability `checkout: false`, `EXTERNAL_CHECKOUT_AUTHORIZED = False`), OPERATIONALLY UNVERIFIED |
| Provider selection / SecretStore slots (4) | IMPLEMENTED, TESTED; credentials never activate anything |
| Commercial terms, price mappings | IMPLEMENTED, TESTED; none seeded; admin mapping registration NOT IMPLEMENTED |
| Checkout service and candidate checkout API | IMPLEMENTED, TESTED, DISABLED, OPERATIONALLY UNVERIFIED |
| Webhook route, signature verification, durable events | IMPLEMENTED, TESTED, DISABLED (`STRIPE_WEBHOOK_AUTHORIZED = False`), OPERATIONALLY UNVERIFIED |
| Background processing, leases, backoff | IMPLEMENTED, TESTED (jobs exist; no scheduler runs) |
| Provider-state reader | `FakeStateReader` TESTED; `NullStateReader` is the runtime default; `StripeStateReader` PARTIALLY IMPLEMENTED (fake-client tests only), NOT WIRED, OPERATIONALLY UNVERIFIED |
| Reconciliation service | IMPLEMENTED, TESTED against fixtures only |
| Entitlement bridge / policy | IMPLEMENTED, TESTED; runtime policy UNAPPROVED (no grant or revoke at runtime) |
| Candidate billing summary | IMPLEMENTED, TESTED (offline data only) |
| Billing Admin operations, recovery actions | IMPLEMENTED, TESTED; recovery REFUSED with the Null reader |
| Reconciliation scheduler | IMPLEMENTED, TESTED, DISABLED (`RECONCILE_SCHEDULER_ENABLED = False`) |
| Seller-initiated refund execution, Admin price-mapping UI, invoice display | NOT IMPLEMENTED (by design) |
| Migrations 0028, 0029, 0030 | IMPLEMENTED, TESTED (fail-closed downgrades from 0029 and 0030) |

## 3. Billing data flow and trust boundaries
```
Candidate browser ──(authenticated, plan code only)──> Checkout API ──> CheckoutService ──> BillingProvider ──> [Stripe hosted checkout]
                                                          server decides price, currency, URLs, idempotency
Stripe ──(signed POST, raw body)──> Webhook route ──> signature + environment ──> DURABLE event row (outbox)
                                                                                         │ lease claim (job or sweep)
                                              Provider-state reader (authoritative read, never the event body)
                                                                                         │ ownership + price + environment + stale/terminal guards
                                                   billing_provider_links (verified) ──> entitlement bridge ──(approved policy only)──> subscriptions
Admin ──(permission)──> read models ;  Admin ──(permission, reason, idempotency)──> recovery ──> the SAME pipeline
```
| Boundary | Input trust | Becomes authoritative only after |
|---|---|---|
| Browser -> API | untrusted | authentication; the body carries a plan code only (`extra=forbid`) |
| Browser return URL | untrusted | never: recorded as a fact (`browser_returned_at`), grants nothing |
| API -> checkout -> provider | authenticated | server-side terms, active mapping, trusted origin, stable provider idempotency key |
| Stripe -> webhook | untrusted | HMAC over the raw body, timestamp both directions, configured environment, allow-listed type, size limit |
| Event store -> worker | provider-verified (as a TRIGGER) | claim under a lease; the body is never the truth |
| Reader -> reconciliation | provider-verified state | owner via our own checkout record, price equals terms, environment, newer than last applied, not a terminal reactivation |
| Reconciliation -> bridge | locally reconciled | explicit policy approval; manual assignments never overridden |
| Admin -> operations/recovery | authenticated + permission | record identity, reason, idempotency key; refused without a reader |

## 4. Threat model and findings
Classification follows evidence: **confirmed** (reproduced by a test or shown in code) versus **PROVIDER VALIDATION REQUIRED** (cannot be settled offline). No hypothetical issue is reported as a bug.
| ID | Sev | Finding | Evidence | Status |
|---|---|---|---|---|
| F1-07 | **HIGH** (gate for activation; not exploitable today, no live subscription can exist) | Account deletion cannot cancel a live provider subscription: the candidate could keep being billed by the seller of record while Ask4Mo holds no record; later events quarantine as `checkout_mismatch`. | `test_F1_07_...` pins current behaviour | **OPEN, owner/legal decision** (section 11); gate for F3 |
| F1-01 | MEDIUM | Different events for the SAME new subscription processed concurrently: the losers were quarantined as `duplicate_subscription` (needs operator review). | reproduced 6 of 6 runs; `test_F1_01_...` | **FIXED** (a lost race on a unique key is a bounded retry, `concurrent_update`; converges with one link, one grant, one applied decision) |
| F1-02 | MEDIUM | Checkout `expires_at` was exactly `now + 30 min`, Stripe's minimum measured from ITS creation time; latency would make it invalid. | `test_C06`, `test_F1_02` | **FIXED** (+5 minute margin; the local attempt still ends first). PROVIDER VALIDATION REQUIRED for the exact limits |
| F1-06 | MEDIUM | Account deletion left `billing_checkout_sessions`, `billing_provider_links`, `billing_entitlement_decisions` orphaned on databases that do not enforce FKs (SQLite); PostgreSQL cascaded. | reproduced; `test_F1_06_...` | **FIXED** (explicit child-first delete; events keep only opaque ids with the link reference cleared; the recovery trail is anonymised) |
| F1-04 | MEDIUM (hardening; not reproducible on SQLite) | Two workers reconciling one subscription could, on PostgreSQL READ COMMITTED, let an older observation commit over a newer one. | code path; `test_F1_04` compiles the lock | **HARDENED** (`SELECT ... FOR UPDATE` on the link row) |
| F1-03 | LOW | An unauthenticated caller could grow the audit log: every request to the (disabled) webhook wrote audit rows. | `test_F1_03_...` | **FIXED** (no audit while the route is off or unconfigured; a verification failure is audited once, after the gate; rate limit unchanged) |
| F1-05 | LOW | Reusing an Idempotency-Key for a different recovery request was a server error (key namespace is global). | `test_F1_05` (HTTP and service) | **FIXED** (409) |
| F1-08 | LOW | The candidate overview titled an administrator-assigned Premium account "Free plan". | `F1-08` unit test | **FIXED** (neutral "No paid subscription", all 8 locales) |
| F1-09 | LOW (test infrastructure) | `test_reporting_w10_12` pinned its clock to 2026-10-15 12:00 UTC while recording telemetry at real time: six tests failed after that instant (reproduced identically on unmodified `main`). | run on `main` and on this branch | **FIXED** (clock follows the run; windows unchanged) |
| F1-10 | LOW | Operations overview "pending checkouts" count was approximate. | code | **FIXED** (exact NOT EXISTS) |
| F1-11 | INFO | A recovery interrupted before its audit commit stays `requested` (the outcome of the verified pipeline already committed, once). Fail-closed by design; replay returns the stored `requested`. | `test_C22` | ACCEPTED |
| P-1 | INFO | The browser accepts only `https://checkout.stripe.com`; if Managed Payments sessions use another hosted host the button fails closed. | `trustedCheckoutUrl` | **PROVIDER VALIDATION REQUIRED** (F2) |
| P-2 | INFO | Webhook events are accepted only at the pinned API version `2026-09-30.endive`; an endpoint on another version is recorded as `ignored` (visible in Admin counts), never reconciled. | `stripe_events.SUPPORTED_API_VERSIONS` | F2 prerequisite: create the endpoint at the pinned version |
| P-3 | INFO | Contracts assumed from documentation: `checkout.sessions.list(subscription=...)`, the payment to invoice-payment to invoice parent lookup, `managed_payments[enabled]` shape, `charge.refunded` as the refund signal under Managed Payments. | fake-client tests only | **PROVIDER VALIDATION REQUIRED** |

Threat scenarios examined with a verdict (all controls verified by tests unless noted): forged checkout success (no success endpoint; return is a fact), client price/currency manipulation (`extra=forbid`, server terms), ownership spoofing (only through our checkout record; customer rebind/swap refused), webhook forgery/replay/duplicate/out-of-order (signature, tolerance both ways, unique id, authoritative reads), provider object substitution (price and terms must equal the checkout), cross-candidate assignment (refused), sandbox/live confusion (environment checks, separate slots, live refused), credential leakage (per-client keys, bounded error categories, secret scans), admin escalation and unauthorised recovery (persona matrix over real HTTP; no path to Premium), refund approval bypass (recovery creates no approval/refund; provider facts are recorded without approval), duplicate subscription and double charge (one open attempt, live-subscription refusal, stable provider key, crash-window tests), stale grants/revocation (stale and terminal guards; newer grant protected), financial record deletion (nothing deletes evidence; downgrades fail closed; F1-06/07), open redirect and Host header (configured origin only; browser allow-list), provider unavailable and crashes and races (retry, lease, rollback, locking).

## 5. Stripe Managed Payments contract assessment
Verified in code and tests: `managed_payments.enabled = true` and `mode = subscription` are mandatory and checked before any client is built (`require_managed_payments`); there is no fallback to ordinary Stripe Payments; no candidate-controlled parameter (customer, email, payment methods) is sent; the provider idempotency key is stable per local record; credentials are per-client, never the SDK's global key, sandbox only, no automatic retries; provider exceptions are reduced to bounded categories with no message text; a malformed response never becomes an open checkout; live is refused by construction. **PROVIDER VALIDATION REQUIRED:** P-1, P-2, P-3 above, sandbox availability of Managed Payments for the seller, and whether the Link management experience is available (no URL is shown).

## 6. Kill switches
`LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED` and `PAID_ENTITLEMENT_POLICY_APPROVED` are all `False` and unchanged. Tests prove: no source file assigns any of them outside the policy module; configuration plus credentials alone activate nothing (a perfectly signed event is still refused; the adapter still refuses); credential rotation changes readiness only; an approved price mapping cannot bypass checkout authorisation; each switch flipped alone enables nothing else (checkout alone: no credential, capability still false; scheduler alone: no job without a reader; webhook alone: events stored, reader Null, policy unapproved, no grant; live alone: still refused and no live client can be built).

## 7. Financial idempotency and failure injection
Verified deterministic and duplicate-free: checkout initiation (same key, different key, 8 concurrent attempts, one provider session), provider session creation (crash after the local row and before the provider call resumes; crash after the provider answered and before the local update re-sends the SAME provider key and yields one session; a stale `pending_creation` row never blocks the candidate; retries bounded at five), webhook acceptance (duplicate, concurrent, two signatures), event persistence (failure is a retryable 503, never an acknowledgement; enqueue failure recovered by the sweep), processing (lease claim, abandoned-lease reclaim, rollback on a crash after the bridge ran), reconciliation, entitlement (a replay never extends or duplicates), recovery (replay returns the stored outcome; concurrent retries process once), scheduler (one job per bucket under concurrency; enqueue failure leaves nothing partial). Injected: database failure at acceptance, Stripe client timeout, malformed provider response, signature failure, worker interruption, entitlement persistence failure, audit write failure, scheduler interruption: no fabricated payment, no unverified grant, no duplicate side effect.

## 8. Subscription lifecycle, reconciliation and entitlement correctness
Checkout, payment, subscription and entitlement are separate everywhere. Covered with deterministic provider fixtures: new, renewal, payment failure, past due, recovery, scheduled and immediate cancellation, expiry, provider cancellation, completed refund, dispute, reactivation refused for a canceled provider id, a new purchase after cancellation (new provider id, new checkout, granted), two simultaneous attempts, a late event for the old subscription (cannot revoke the newer grant), missing/duplicate/delayed/out-of-order/stale events, provider timeout/unavailable/missing object, unknown owner, ownership conflict. State converges from the provider read, not from arrival order or timestamps; a failed read never proves payment. Entitlements: none from a redirect, an unsigned or unverified event, unapproved terms, an unknown subscription, an unpaid invoice or the frontend; none across candidates; no duplicate grant; admin and migration assignments are never overridden or revoked; the synthetic policy is refused in hosted environments; the runtime policy is unapproved.

## 9. Webhook security (requalified)
Raw-body HMAC with the configured environment's secret only; timestamp tolerance in both directions; 256 KiB limit; explicit 14-event allow-list; environment and structure validation; unique event identity per provider, environment and id; replay inside the window idempotent and outside rejected; an invalid signature never reaches acceptance, processing or the bridge (spied); stored events hold no payload, personal or card data and the audit holds no secret or signature (scanned); durable acceptance before acknowledgement; crash recovery by lease and sweep.

## 10. Authorization, recovery permission and approvals
Admin billing routes are permission-gated and verified for every persona; candidates, support, security/privacy and knowledge admins get 403; billing admin cannot rotate Stripe credentials (owner only, step-up); provider ids are masked; raw bodies are inaccessible; recovery needs a record id, a reason and an idempotency key and creates no approval, refund or grant.
**UPDATE (W12.4D-F1R): the owner approved option C and F1-07 is code-remediated; see `W12_04D_F1R_ACCOUNT_CLOSURE_RECOVERY_RBAC.md`.** **Recovery permission assessment.** Today `operations_admin` (and the owner) can recover via `platform.jobs.manage` and cannot read billing diagnostics; `billing_admin` can read and cannot recover. No exploit exists: a recovery only re-drives the existing verified pipeline, is refused while the reader is Null, and creates no financial or entitlement authority beyond the unapproved policy. The structural weakness is that, once a real reader exists, recovery would be performed without sight of the financial state it changes. Options: (A) keep the split: least privilege on paper, blind operation in practice; (B) give `billing_admin` `platform.jobs.manage`: **rejected**, it also governs knowledge, privacy and account-deletion jobs; (C) add `platform.billing.recover` held by `billing_admin` and the owner, require it (instead of `platform.jobs.manage`) on the three recovery routes, require a fresh step-up for `reconcile` and `retry` once a real reader exists, keep reason, idempotency and same-transaction audit. **Recommendation: (C)** (registry 43 to 44). Two-person approval is not required for recovery because it moves no money and grants nothing directly; entitlement effects remain policy-governed. **This is an OWNER decision; nothing was added.**
Financial approvals: two-person approval for price changes and seller refunds is unchanged and enforced by constraint; a provider-initiated refund, cancellation or dispute is recorded as a fact without any Ask4Mo approval; recovery cannot bypass or suppress either.

## 11. Scheduler, migrations, audit, privacy and retention
**Scheduler:** one job per 15-minute bucket across concurrent instances; interrupted ticks leave nothing partial; the job system provides leases, bounded retries and visibility; it makes only fake-reader calls in tests; disabled by constant and without a reader; no Admin control enables it. Conditions for safe activation (all required): a wired sandbox `StripeStateReader` validated in F2; an owner-approved entitlement policy; Managed Payments eligibility confirmed; the sweep validated against real sandbox data; an operational owner and alerting on `needs_review`; a reviewed change to the constant.
**Migrations:** fresh upgrade, stepwise upgrade from 0027/0028/0029, re-application, schema constraints (unique/partial indexes, FK delete rules: user data cascades, terms history RESTRICT, operator trail SET NULL), and fail-closed downgrades over financial history, all on isolated databases, with no stamping and no `create_all`.
**Audit:** checkout, webhook acceptance/duplicate/ignored/rejection, processing, reconciliation, entitlement decision, recovery request and outcome (same transaction), event-detail views, approvals: correlated by ids; no secret, token, card or content; retries produce no duplicate audit facts (replay writes none; F1-03 removed pre-verification rows).
**Data inventory:** technical records (jobs, events outbox), financial evidence (events, links, decisions, price mappings, recovery actions), personal information (none stored: opaque ids only; candidate id is the only person-link), audit evidence (`audit_events`, append-only). Candidate deletion now removes the candidate's checkout attempts, links and decisions on every database (F1-06); events remain (opaque ids), the operator trail is anonymised. **Unresolved legal questions (no period invented):** retention of events, links, decisions and recovery records; effect of provider-side deletion (Stripe cancels subscriptions and deletes its data); and the HIGH finding F1-07: whether erasure must be blocked or must trigger cancellation first.

## 12. Commercial and policy decision register (none decided, no price seeded, EUR 19.99 remains a preview)
| Decision | Effect on implementation | Options | Recommendation | Risk of postponement |
|---|---|---|---|---|
| Premium monthly price | terms and mapping; pricing page | set an approved amount via two-person terms | owner | no sandbox price to map; F2 cannot create a sandbox product honestly |
| Premium annual price | second interval/mapping, UI | offer or defer | defer unless wanted | none until offered |
| Billing currency | terms, mapping | EUR only or localised | EUR only first (Managed Payments localises display) | wrong currency in sandbox product |
| Trial availability | `trial_grants` policy | none, 7, 14 days | none first | trial rule is `hold` (no access) meanwhile |
| Tax-inclusive display | pricing copy | inclusive, exclusive | follow Link/Stripe presentation | misleading price copy |
| Cancellation policy | `canceled` rule; copy | at period end, immediate | at period end (provider default) | `hold`: no revocation |
| Refund policy | `full_refund` rule | revoke, keep | revoke on full refund | `hold` |
| Failed-payment grace | `past_due` rule | keep N days, revoke | keep during provider retries | `hold` |
| Dispute access | dispute rules | keep while open, revoke when lost | keep open, revoke lost | `hold` |
| Supported countries | eligibility and copy | all Managed Payments countries or subset | provider list minus blocked | legal exposure |
| B2B subscriptions | out of scope today | defer | defer | none |
| Legal seller entity | Stripe account, terms | German entity (as noted in the assessment) | owner | blocks the account |
| Financial-data retention | deletion and archive rules | owner/legal | legal review | unbounded retention by default |
| **Account deletion with a live subscription (F1-07)** | deletion flow | block until cancelled in Link; or provider-side deletion only; or cancel then delete | **block with explicit guidance, plus retain opaque financial evidence** (owner/legal) | candidate could keep being charged |
| Billing recovery permission | RBAC | A, B (rejected), C | **C** | blind recovery once a reader exists |
| Managed Payments eligibility | everything | owner applies | owner | no sandbox, no F2 |

## 13. Qualification results (measured, with limits)
Billing test files, collected tests: `test_billing_w10_5` 24, `test_stripe_foundation_w12_4d_b` 37, `test_checkout_w12_4d_c` 54, `test_webhooks_w12_4d_d` 114, `test_billing_ops_w12_4d_e` 61, `test_billing_f1_qualification` 48 (338 billing tests; F1 added 48). By control id in the F1 file (sums to 48 collected tests): C01-C05 kill switches (5); C06-C10 provider contract (5); C11-C16 checkout idempotency and crash windows (6); C17-C19 webhook (3); C20-C21 reconciliation failure (2); C22-C25 authorization, recovery and candidate (4); C26-C27 lifecycle (7, including six parametrised cases); C28-C30 migrations (3); C31-C32 scheduler (2); C33 data inventory (1); F1-01 to F1-07 defect regressions (8, including F1-05b); the end-to-end simulation (1); the component inventory (1). The offline end-to-end test exercises: checkout through a recording fake, persisted attempt, signed webhook, durable acceptance, reconciliation, synthetic policy grant, payment failure and recovery, scheduled then effective cancellation, stale replay, replacement subscription, late old-subscription event, dispute, full refund and a cross-candidate attack; final state asserted deterministic. **Measured (this branch, final code):** backend 3670 collected, 3666 passed, 4 skipped, 0 failed, 0 errors; frontend 937 unit tests passed with typecheck, lint and build clean; Playwright 341 passed, 0 failed; 43 CI evaluators exit 0 (41 print an explicit PASS; `eval_knowledge_expansion` prints no PASS line; `eval_product_coverage` exits 0 but reports 94% insufficient evidence, n = 412, BELOW GATE, unchanged); `ruff` and `git diff --check` clean; protected-store fingerprints unchanged. **Not measured:** line or branch coverage (`coverage` is not installed; no percentage is claimed) and assertion counts (not instrumented). **Risks accepted:** F1-11, P-1 to P-3 until F2. **Risks remaining:** F1-07, all provider assumptions, no live validation of any boundary.

## 14. Operational readiness matrix
| Item | State |
|---|---|
| Stripe account available | BLOCKED (owner) |
| Managed Payments eligibility confirmed | POLICY DECISION REQUIRED / BLOCKED |
| Sandbox access available | BLOCKED (depends on the account) |
| API credential configured | CONFIGURATION REQUIRED |
| Webhook signing secret configured | CONFIGURATION REQUIRED |
| Provider-state reader operational | IMPLEMENTED BUT UNVERIFIED (not wired) |
| Checkout authorised | CONFIGURATION REQUIRED (code constant, reviewed change) |
| Webhooks authorised | CONFIGURATION REQUIRED (code constant, reviewed change) |
| Reconciliation scheduler operational | IMPLEMENTED BUT UNVERIFIED (disabled) |
| Approved commercial terms | POLICY DECISION REQUIRED |
| Approved entitlement policy | POLICY DECISION REQUIRED |
| Billing recovery authorisation approved | POLICY DECISION REQUIRED |
| Candidate billing operational | IMPLEMENTED BUT UNVERIFIED |
| Admin diagnostics operational | IMPLEMENTED BUT UNVERIFIED |
| End-to-end sandbox validated | NOT IMPLEMENTED (F2) |
| Live deployment approved | BLOCKED |
Nothing is READY and nothing offline-qualified is called production-ready.

## 15. F2 prerequisites (technical handoff; nothing configured in this wave)
Account: a Stripe account with Managed Payments eligibility accepted and sandbox access confirmed by the owner. Owner decisions first: price and currency for a sandbox product (non-binding), the entitlement policy to use in the sandbox (synthetic until approved), the recovery-permission model, and the F1-07 decision. Credentials: the sandbox secret key and sandbox webhook signing secret **entered by the owner only through Admin (step-up) into the managed SecretStore slots** `STRIPE_SANDBOX_SECRET_KEY` and `STRIPE_SANDBOX_WEBHOOK_SECRET` (never pasted into chat, never in a repository or environment file shared in chat); live slots stay empty. Non-secret configuration: `BILLING_PROVIDER=stripe_managed_payments`, `STRIPE_ENVIRONMENT=sandbox`, `ASK4MO_APP_BASE_URL` (https), `SECRET_STORE_BACKEND=encrypted_database` with a deployment-managed key. Webhook: a sandbox endpoint created at API version `2026-09-30.endive` subscribed to exactly the 14 allow-listed events. Reader: wire `StripeStateReader` for the sandbox environment only, behind a reviewed change, with the Managed Payments assumptions P-1 to P-3 verified. Code gates to flip (reviewed change, sandbox only): `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`; the scheduler constant only after the sweep is validated. Environment separation: sandbox and live never share a slot, host or configuration. Authorisation boundary: only the owner-approved test sequence, from the owner's own test candidate, sandbox cards only. Expected external calls: Checkout Session create, subscription/checkout/session retrieval and list, invoice-payment list and invoice/charge retrieval, and inbound sandbox webhooks. Testing infrastructure: a public HTTPS tunnel or the Stripe CLI to deliver sandbox webhooks locally. Rollback: set the constants back to `False` (reviewed change), remove the sandbox credentials in Admin, restart the API and worker; stored events and links remain as evidence (the `0029` and `0030` downgrades refuse over history). Readiness verification: the Admin readiness panel plus a documented checklist run, with results recorded.

## 16. F3 acceptance criteria
End-to-end sandbox run: purchase, renewal, payment failure and recovery, scheduled and immediate cancellation, refund, dispute, replacement purchase and a cross-candidate attempt, each reconciled correctly; replayed and out-of-order sandbox events converge; the Link management and receipt experience observed and the correct destination verified before any URL is shown; P-1 to P-3 resolved; F1-07 resolved by an owner/legal decision and implemented; an approved entitlement policy and approved terms in place; the recovery-permission decision implemented; the scheduler validated and its activation conditions met; operational runbook and alerting accepted; no kill switch changed for live; security re-review of any code touched in F2.

## 17. Programme status
W12.4A COMPLETE; W12.4B COMPLETE; W12.4C ENGINEERING COMPLETE, LIVE BREVO VALIDATION DEFERRED; W12.4D-A to E COMPLETE; **W12.4D-F1 SECURITY QUALIFICATION IN PROGRESS (code qualified here, awaiting remote checks and merge)**; W12.4D-F2 NOT STARTED; W12.4D-F3 NOT STARTED; W12.4E NOT STARTED; W12.4F NOT STARTED; W12.5 NOT STARTED; RC-P10-004 NOT CREATED; AC-24 PARTIAL; P10C NOT STARTED. The `eval_product_coverage` metric (94% insufficient evidence, n = 412, BELOW GATE) is unchanged and remains a tracked quality follow-up; exiting 0 is not a pass.

## 18. Recommended next actions
(1) Owner: decide F1-07, the recovery permission, price/currency, entitlement policy and Managed Payments eligibility. (2) Merge F1 after remote checks. (3) Only then authorise F2 and supply credentials through Admin.
