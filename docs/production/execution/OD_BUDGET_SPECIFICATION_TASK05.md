# OD-BUDGET — owner-controlled specification

Status: **OPEN / UNAPPROVED**. This is a decision worksheet, not an authorization,
runtime configuration, pricing table or approval marker. All approval fields below
are deliberately blank. Synthetic fixtures in tests are not proposals or approvals.

| Required decision | Owner-approved value |
|---|---|
| Budget owner | |
| Approver | |
| Approved environment | |
| Budget period start and expiry (UTC) | |
| Currency (runtime ledger supports USD) | |
| Total hard spending ceiling | |
| Lower operational stop threshold | |
| Total maximum provider requests | |
| Development allocation and request ceiling | |
| Evaluation allocation and request ceiling | |
| Production allocation and request ceiling | |
| Agent category hard/stop allocation per class | |
| Interview category hard/stop allocation per class | |
| Embedding category hard/stop allocation per class | |
| Evaluation category hard/stop allocation per class | |
| Approved provider hosts | |
| Approved exact model IDs | |
| Per-model prompt/completion price per token | |
| Price verification sources/effective dates/expiry | |
| Maximum input/output tokens | |
| Request connect/read/write/pool timeouts | |
| Maximum retries and dedupe window | |
| Cross-process provider concurrency | |
| Permitted evaluation datasets and purposes | |
| Approval marker reference (never actual value here) | |
| Protected configuration/marker delivery and custody | |
| Emergency stop procedure and operator | |
| Reconciliation owner | |
| Incident owner and escalation | |
| Approval date and signed evidence reference | |

The owner must supply and approve the complete private JSON and separately supply
a matching marker through approved runtime secret delivery. Nobody should copy
values from a synthetic fixture. Config generation, image building, CI and Compose
do not authorize spending. Staging must remain killed/closed until explicit
approval and live verification authorization exist.

The existing JSON sections `currency`, `classes`, `limits`, `pricing.models`,
`allowed_provider_hosts` and `approval_marker` are retained. Hosted use additionally
requires `total` (`hard_cap_usd`, `stop_usd`, `max_requests`) and `approval` containing
`owner`, `approver`, `environment`, `currency`, `period_start`, `expires_at`,
`pricing_effective_at`, `pricing_expires_at`, `pricing_source`,
`reconciliation_owner`, `incident_owner`. Dates must have timezone offsets.
No real configuration example is supplied. Pricing must exactly name served
models; a missing model refuses before network activity. Missing categories refuse.
Explicit evaluation authorization/datasets must accompany any later live evaluation
request; this document does not grant it.

Changing the configuration or starting a new period requires a drained, authorized
ledger reconciliation. The policy hash is durable; the application refuses a new
hash rather than resetting existing spending. No operator may zero unknown usage
or clear a kill merely because a new image or configuration exists.
