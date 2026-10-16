# W12.4D-F2-B1R: webhook financial event safety

Status: **CODE QUALIFIED OFFLINE. Unsupported-version financial webhook events are durable, actionable and fail closed. Sandbox validation pending.**
No Stripe call, no webhook registered, no provider read enabled, no checkout, no live billing, no paid product or price, no paid entitlement. No migration (Alembic head `0031_account_closure`).
Starting point: `main` `8de4e8ec3ec1f8b4badfe444aadee9653c57e8c6` (PR #164, F2-B1 merged).

## 1. The defect (from F2-B1 section 9)

A validly signed financial event whose `api_version` is not the pinned `2026-09-30.endive` was stored as `ignored` (category `unsupported_api_version`) with `processed_at` set at acceptance:
excluded from `awaiting_operator` and from the reconciliation attention list, not recoverable (`recoverable` only for failed, needs_review, quarantined), no alert. If a future webhook endpoint were created with a different API
version, every payment, cancellation, refund and dispute would be silently discarded and, with the scheduler disabled, paid access could stay stale. It was a liveness gap, not an unsafe-grant gap.

## 2. Event taxonomy and exact transitions (after the fix)

| Class | Where decided | Status and category | Counted for operators | Recoverable |
| --- | --- | --- | --- | --- |
| Invalid or missing signature, bad timestamp, wrong environment, oversize, malformed JSON or envelope | receiver, before storage | rejected (4xx), nothing stored | audit only | n/a |
| Connect-style `account` context | `accept` | `ignored` / `unexpected_account_context` | no | no |
| Irrelevant event type (any version) | `accept` | `ignored` / `unsupported_event_type` | no | no |
| Supported financial type, supported version | `accept` then `process` | `received` then processed, retry, quarantined or needs_review | yes if not processed | yes |
| **Supported financial type, unsupported or missing version** | `accept` | **`needs_review` / `unsupported_api_version`**, `processed_at` null, reference-only payload | **yes: `needs_review`, `awaiting_operator`, `held_unsupported_api_version`** | **yes (authorized recovery, authoritative read)** |
| Supported-version subscription event with no usable subscription id (malformed) | `process` | `needs_review` / `malformed_financial_event` | yes | yes |
| Held event whose reference cannot be resolved by an authoritative read | recovery | `needs_review` / `unresolvable_reference` | yes | yes |

Ordering fix: the event type is now classified before the version, so an irrelevant event under an old version is `unsupported_event_type`, not mislabelled as a version problem.
The route still acknowledges a held event with 2xx: it is durably stored, so Stripe must not retry it forever.

## 3. What is stored for a held event (no interpretation of the incompatible payload)

`normalized_json = {"kind", "api_incompatible": true, "object_id"}`. `object_id` is the opaque `data.object.id`, kept only when it is a well-formed id whose prefix matches the kind the event type promises
(`sub_`, `in_`, `cs_`, `ch_`, `dp_`); otherwise it is null. Customer, status, amounts, refund and dispute fields are never read. The envelope's `data.object.id` position is the generic Stripe event envelope, not a version-specific schema;
no new event schema was invented. The id is an untrusted lookup key for an authoritative provider read, never evidence.

## 4. Recovery path (auditable, authoritative-read only)

Held events are never claimed by the worker or the sweep (only `received`, `failed` and an abandoned `processing` lease are runnable), so nothing happens automatically. An administrator holding `platform.billing.recover` with fresh step-up uses the
existing "retry event" action (idempotency key, reason, audited in the same transaction, bounded operator retries). It is refused (`reader_unavailable`) while the reader is the Null reader, which is the runtime state. When a real reader exists,
`_reconcile_incompatible` resolves the subscription only through the provider: subscription id directly; checkout session via `checkout_session`; invoice via `get_invoice`; refund via `subscription_for_payment(charge)`; dispute via `get_dispute` then
`subscription_for_payment`. Then the ordinary guards apply: trusted checkout ownership (never email), price and terms match, environment match, stale snapshot and terminal-state protection, entitlement bridge under the approved policy only.
The reconciliation record carries `incompatible_payload: not_interpreted`. **Refund and dispute facts are NOT taken from an incompatible payload** (`_merge_facts` receives none); they are recorded only by a compatible event or by a validated read.
Consequence for F2-B2: whether a refund or dispute needs an authoritative charge or refund read to update `refund_state` and `dispute_state` is a SANDBOX VALIDATION REQUIRED item (the F2-A reader has `get_refund` and `get_dispute`, but the link facts are still fed only by compatible events).

## 5. Admin visibility

`overview.events.held_unsupported_api_version` (count of held or retrying version events), included in `awaiting_operator` through `needs_review`; the reconciliation view groups `needs_review:unsupported_api_version`; the event detail classification
reads "Held: a validly signed financial event arrived under an unsupported API version... Check the webhook endpoint's API version"; the event list filters by `needs_review`. Alert delivery beyond in-app counts (email or paging) is not part of this wave. The Admin billing UI is part of the not-started W12.5 work.

## 6. Preserved controls (unchanged and re-tested)

Signature verification (raw body, tolerance both directions), idempotency (duplicate incompatible event is one row, disposition `duplicate`), environment isolation (a live-flagged event to a sandbox deployment is refused before storage), ownership through the trusted checkout record,
entitlement bridge as the only writer of provider entitlements under an owner-approved policy (the unapproved runtime policy grants nothing even after recovery), 44 permissions, `platform.billing.recover` plus fresh step-up (operations admin, support and others get 403),
financial approvals. All activation constants stay False: `LIVE_BILLING_ENABLED`, `EXTERNAL_CHECKOUT_AUTHORIZED`, `STRIPE_WEBHOOK_AUTHORIZED`, `RECONCILE_SCHEDULER_ENABLED`, `PROVIDER_READS_AUTHORIZED`, `PAID_ENTITLEMENT_POLICY_APPROVED`.

## 7. Tests

`tests/test_billing_f2b1r_webhook_financial_safety.py` (40 cases): compatible event unchanged; invalid signature stores nothing; irrelevant types ignored under any version; each of the five financial kinds held with reference only;
prefix mismatch dropped; malformed subscription event reviewed, not ignored; duplicate incompatible event is one attention item; environment isolation; Admin counts, listing, detail and classification (also over HTTP);
held cancellation neither revokes nor is claimed by worker or sweep; authorized recovery of a cancellation where the payload lies and the provider's state wins; refund recovery without applying payload facts; invoice and dispute recovery through reads;
unresolvable and unknown-ownership events stay in review; stale and terminal protection; Null reader leaves the event untouched; unapproved policy grants nothing; unauthorized roles get 403; step-up required and Null reader refuses; accept path cannot reach the bridge.
Two existing tests that asserted the old `ignored` behaviour were updated to the corrected contract (`test_webhooks_w12_4d_d.py`, `test_billing_f2a_stripe_readiness.py`); no security assertion was weakened.

## 8. Remaining sandbox validation (F2-B2 and F3)

Create any future webhook endpoint with the pinned API version and treat a held version event after go-live as a configuration incident; confirm the real event envelope for Managed Payments events; confirm the authoritative reads exist and behave for
refund and dispute resolution; decide whether refund and dispute facts need an authoritative read path; decide on alert delivery beyond in-app counts. Programme dependencies are unchanged (see the F2-B1 document, section 18).
