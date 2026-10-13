# Ask4Mo: Billing Admin Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This document describes what the **billing_admin** role can do **today**, derived from the code-defined permission preset, the frontend destination table and the route permission graph (a read-only derivation, nothing mutated). Anything not built is labelled **PLANNED W12.4**. The role index is [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md); the owner role is [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md).

## 1. Role purpose

Administer plans, plan-version entitlements, subscription assignment and the **MOCK** billing controls (commercial terms, price changes, refunds) and review commercial reporting. **Billing is MOCK in the current runtime.** Authorization is by permission string only; the role name is never checked by any route. The role is a code-defined preset and cannot be customised. It is a delegated, least-privilege operational role, not a junior Platform Admin.

## 2. Permission boundary

**10 permissions:** `platform.overview.read`, `platform.users.read`, `platform.plans.read`, `platform.plans.manage`, `platform.plans.price.change`, `platform.subscriptions.read`, `platform.subscriptions.manage`, `platform.billing.read`, `platform.billing.refund`, `platform.reports.commercial.read`.

Of the 147 Admin API routes this role may call **28**. Note `platform.subscriptions.read` is held but no route requires it today.

## 3. Visible navigation

**5 destinations:** Overview (`/admin`), Users (`/admin/users`, read only), Plans (`/admin/plans`), Billing (`/admin/billing`), Reports (`/admin/reports`, commercial tab only).

## 4. Typical workday / workflow

Sign in -> Overview (mock billing counts) -> Plans (versions and entitlements) -> assign a plan to an account or workspace -> Billing: review **MOCK** invoices and payments -> **propose commercial terms** (price change) -> a **different** eligible administrator approves or rejects -> request a **mock refund** on a succeeded payment -> a **different** eligible administrator approves -> review the commercial report. Each step is audited.

## 5. Key actions

| Action | Permission | Notes |
|---|---|---|
| Create the next plan draft, edit a draft's entitlements, activate or retire a version | `plans.manage` | Active versions are immutable; activation never moves subscribers; no price or quota is invented |
| Assign a plan to an account or workspace | `subscriptions.manage` | An access assignment, not a payment |
| View mock invoices, payments, customers, refunds, terms and approvals | `billing.read` | Labelled MOCK |
| Propose, approve or reject commercial terms (price change) | `plans.price.change` | Requester is not approver |
| Request, approve or reject a mock refund | `billing.refund` | Requester is not approver; runs as a background job |
| View the mock commercial report | `reports.commercial.read` | Mock billing is not live revenue |

## 6. High-risk actions / governance

- **Price changes and refunds need a different active administrator.** The rule is *distinct actor with the required permission*: two different `billing_admin` accounts, or a `billing_admin` and a `platform_admin`, can be the two sides. One account can request but never approve its own request, and there is no override, even for the Platform Admin.
- **No step-up** is required for these actions today (step-up applies only to platform role changes, which this role cannot reach).
- **Billing is not entitlement:** billing state never changes access, and a plan assignment never proves payment. The two are administered by the same role but are separate systems.
- Refunds execute as an idempotent background job, so a worker must be running for a refund to complete.

## 7. What the role cannot do

Change roles, accounts or sessions; manage users (read only); see Support, Security, Audit, Privacy, Legal, Knowledge, Jobs, Integrations, Configuration, Flags or AI; run or retry background jobs; and use anything that would move real money, because **no live provider, checkout, card processing, tax engine, live webhook, live refund or real revenue exists**.

## 8. Candidate-data boundary

| This role **can** see | This role **cannot** see |
|---|---|
| Account metadata (read only), plan and subscription metadata, mock billing records linked to an account | CV, documents, interview answers, Mo conversations, Story Bank, memory, reports |
| Aggregate commercial reporting (mock) | Card or payment-method data (Ask4Mo never holds it) |

Never visible to this role (or to any Admin role, including the 43 / 43 Platform Admin): candidate CVs, raw candidate documents, interview answer text, Mo conversations, Story Bank and private evidence, private preparation memory and candidate report contents. There is no break-glass, no impersonation and no "view as user" permission.

## 9. Current operational limitations

- **CURRENT - MOCK.** The only provider is `MockBillingAdapter`, enabled only in development or test environments. Not built: real checkout, live payment provider, real card processing, live invoices and refunds, tax handling, live webhooks, production reconciliation, coupons and revenue or MRR reporting.
- The role holds no job permission, so it cannot see the queue or worker state that a refund depends on (see finding SJA-03).
- Owner-walkthrough findings tracked, not fixed: F-05 (billing request forms open off screen), F-11 (refund amount in minor units), F-10 (Plans says no prices while Billing holds mock terms).

## 10. Escalation to Platform Admin

Escalate for: role or account changes, a refund stuck because no worker is running (Operations Admin or Platform Admin hold the job permissions), provider or configuration problems once a live provider exists (Operations Admin or Platform Admin), security issues (Security / Privacy Admin or Platform Admin) and any AI, knowledge or privacy question (their respective roles or the Platform Admin).

## 11. Planned W12.4 impact

**PLANNED W12.4D, Live Billing Provider** (checkout, provider customer and subscription mapping, webhooks, invoices, payments, refunds, reconciliation, Admin configuration and status) is the main future change for this role, with the Operations Admin involved where provider health is concerned. It is not current, the provider is not chosen, and billing will remain separate from entitlement. W12.4F may revisit which operational views this role needs.

## 12. Route reference

| Page | URL |
|---|---|
| Overview | `/admin` |
| Plans | `/admin/plans`, `/admin/plans/{id}` |
| Billing | `/admin/billing` |
| Reports (commercial) | `/admin/reports` |
| Users (read only) | `/admin/users`, `/admin/users/{id}` (the account page offers plan assignment) |
