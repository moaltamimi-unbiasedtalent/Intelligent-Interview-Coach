# Ask4Mo: Operations Admin Journey

**Status: CURRENT / CANONICAL.**
**Qualified against:** `main` at `13c9c40ea054ad3301b322ce1903fcdb28321ee9` (2026-10-13).

This document describes what the **operations_admin** role can do **today**, derived from the code-defined permission preset, the frontend destination table and the route permission graph (a read-only derivation, nothing mutated). Anything not built is labelled **PLANNED W12.4**. The role index is [SPECIALIST_ADMIN_JOURNEYS.md](SPECIALIST_ADMIN_JOURNEYS.md); the owner role is [PLATFORM_ADMIN_JOURNEY.md](PLATFORM_ADMIN_JOURNEY.md).

## 1. Role purpose

Operate the platform's runtime: background jobs and workers, integration and provider status, the durable platform pause, restriction-only feature flags, operational and AI-economics reporting, and read access to AI configuration and diagnostics. Authorization is by permission string only; the role name is never checked by any route. The role is a code-defined preset and cannot be customised. It is a delegated, least-privilege operational role, not a junior Platform Admin.

## 2. Permission boundary

**11 permissions:** `platform.overview.read`, `platform.jobs.read`, `platform.jobs.manage`, `platform.integrations.read`, `platform.integrations.manage`, `platform.flags.read`, `platform.flags.manage`, `platform.config.manage`, `platform.releases.read`, `platform.reports.read`, `platform.ai.read`.

Of the 147 Admin API routes this role may call **38**. `platform.releases.read` is held but no route requires it today (finding SJA-06). The role does **not** hold `platform.integrations.secret.rotate`.

## 3. Visible navigation

**9 destinations:** Overview (`/admin`), Review / Diagnostics (`/review`), Reports (`/admin/reports`), Configuration (`/admin/configuration`), Feature flags (`/admin/flags`), AI and models (`/admin/ai`, read only), Jobs (`/admin/jobs`), Integrations (`/admin/integrations`) and Provider status (`/admin/providers`).

## 4. Typical workday / workflow

Sign in -> Overview -> **Jobs**: check workers seen and the queue, inspect failures, retry or cancel -> **Integrations**: review configuration, runtime and health; run a **bounded manual connection test** where supported -> **Provider status** -> **Feature flags**: override a code-defined flag -> **Configuration**: pause or resume a capability -> **Reports**: operations, product, quality and AI economics -> AI and models (read only) -> Review / Diagnostics.

## 5. Key actions

| Action | Permission | Notes |
|---|---|---|
| View the queue, workers and job detail | `jobs.read` | Payloads are never shown; failures are fixed categories |
| Queue a no-op diagnostic job, retry a failed job, cancel a queued job | `jobs.manage` | Job types are code-defined; no shell job; a running job cannot be cancelled |
| View integrations and provider status | `integrations.read` | Configuration, runtime and health are separate; values are never shown |
| Run one manual connection test | `integrations.manage` | Available for OpenRouter and ClamAV only; one bounded call, no polling |
| View and change feature flags | `flags.read`, `flags.manage` | Two code-defined flags; override can only **restrict**; reason and expected revision required |
| Pause or resume a capability | `config.manage` | Five capabilities; reason, expected revision and confirmation required; refuses new candidate activity only |
| View operational, product, quality and AI-economics reports | `reports.read` | Aggregates only; small cohorts suppressed; unknown is not zero |
| View AI configuration | `ai.read` | Read only |

## 6. High-risk actions / governance

- **The pause affects candidates**: pausing a capability refuses new candidate activity of that kind with a fixed message (saved data, privacy and account controls, legal pages, Admin recovery and the worker are not paused). It needs a reason, an expected revision and a confirmation, and a stale revision is refused.
- **Flags can only restrict**; they never grant permission, entitlement, billing or AI changes, and there is no generic environment, secret, JSON or database editor.
- **No step-up and no second approver** apply to these actions today. All changes are audited in the same transaction.

## 7. What the role cannot do

Manage users, roles or sessions (it cannot even see Users); change plans, billing or refunds; approve or activate knowledge; manage, evaluate or activate AI configurations; handle privacy requests or legal versions; see Support, Security, Audit or commercial reporting; replace credentials (no rotation permission); and read candidate data.

## 8. Candidate-data boundary

| This role **can** see | This role **cannot** see |
|---|---|
| Job, worker and queue metadata (type, state, safe summary), integration and provider configuration status, pause and flag state, aggregate reports | CV, documents, interview answers, Mo conversations, Story Bank, memory, reports |
| AI configuration and evaluation read state, diagnostics | Credential values, job payloads, per-person data |

Never visible to this role (or to any Admin role, including the 43 / 43 Platform Admin): candidate CVs, raw candidate documents, interview answer text, Mo conversations, Story Bank and private evidence, private preparation memory and candidate report contents. There is no break-glass, no impersonation and no "view as user" permission.

## 9. Current operational limitations

- **Integrations secrets: CURRENT (W12.4B) - this role inspects, never rotates.** Provider credentials are now configurable through a writable encrypted SecretStore, but only with `platform.integrations.secret.rotate` (held only by the Platform Admin) and a fresh password step-up. This role holds `integrations.read` and `integrations.manage`, so it sees each credential's source (managed, environment, not configured), when it was last changed and whether a rotation applies on next use or after restart, and may run the permitted manual connection tests, but the Configure, Replace and Remove controls are **not shown** and the routes return 403. No value, prefix, suffix or mask is ever shown to any role. This boundary is a role-scope finding (see SJA findings), not a change: no preset was altered.
- **Email: CURRENT - ENVIRONMENT MANAGED / UNVALIDATED LIVE.** The Brevo adapter exists; live delivery is unvalidated; Admin has no test email or sender configuration.
- **Provider status is configuration status only**: not the same as healthy, and not the same as live validated. Only OpenRouter and ClamAV have a manual test.
- Jobs have no dead-letter state; a queued job does not imply a running worker.
- **Knowledge is PARTIAL with an owner-reported issue (root cause not diagnosed)**; this role depends on the worker and queue that issue involves.
- Owner-walkthrough findings tracked, not fixed: F-04 (Integrations overflow on narrow screens), F-01 (Review / Diagnostics outside the Admin shell), F-15 (raw environment-variable names on the flags page), F-17 (Integrations and Provider status overlap).

## 10. Escalation to Platform Admin

Escalate for: user, role or session issues (Platform Admin, or Security / Privacy Admin for sessions), refunds or price changes (Billing Admin or Platform Admin), knowledge approval (Knowledge Admin or Platform Admin), privacy execution or legal publication (Security / Privacy Admin or Platform Admin), AI configuration changes (`ai.manage` and `ai.activate`, Platform Admin only), and credential rotation (Platform Admin only, currently technically unavailable).

## 11. Planned W12.4 impact

**PLANNED W12.4, not current.** This role is the most affected: W12.4A (Knowledge Base Accessibility & Operations, the first sub-wave: worker and queue visibility), W12.4B (Secure Provider & Secret Administration), W12.4C (Email & Identity Operations), W12.4D (provider health where a live billing provider exists), W12.4E (Governed Speech Providers) and W12.4F (Admin Configuration Completeness, which classifies every capability and adds governed controls only for normal platform operations, never arbitrary environment variables, commands, filesystem paths or secret values). None is implemented. No permission change is made or promised here.

## 12. Route reference

| Page | URL |
|---|---|
| Overview | `/admin` |
| Jobs | `/admin/jobs`, `/admin/jobs/{id}` |
| Integrations | `/admin/integrations`, `/admin/integrations/{code}` |
| Provider status | `/admin/providers` |
| Feature flags | `/admin/flags` |
| Configuration (pause) | `/admin/configuration` |
| Reports | `/admin/reports` |
| AI and models (read only) | `/admin/ai`, `/admin/ai/{id}` |
| Review / Diagnostics | `/review`, `/review/agent`, `/review/rag`, `/review/evaluation` (outside the Admin shell, F-01) |
