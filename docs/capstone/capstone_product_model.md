# Ask4Mo Capstone — Product & Platform Model

Roles, entitlements, pricing hypothesis, Admin Console, marketing, and the multi-agent decision.
Pricing here is a **product hypothesis**, not a commercial commitment. **No billing** is implemented.

## Roles (orthogonal to entitlements)
- **Platform role:** `USER` (default) | `PLATFORM_ADMIN`/`OWNER`. Enforced server-side.
- **Workspace role:** `WORKSPACE_OWNER` | `WORKSPACE_MEMBER`. Scoped to a workspace; never grants
  blanket access to a member's personal records.
- Current state: **ABSENT** (only transitional `X-User-Subject` identity). Foundation in P1.

## Product entitlements (BASIC / PREMIUM) — separate dimension
Entitlements are a data-driven capability/limit set so a future billing system can flip them without
re-architecting. Enforced **server-side** at the API/service layer; frontend hiding is never the control.

### BASIC (indicative €0)
Core Mo preparation; bounded JD analysis; governed career knowledge + citations/sources; limited
Interview Practice; limited History; basic Progress; limited approved memory; Help/tutorial;
**all privacy/data controls and security protections**.

### PREMIUM (hypothesis €19.99/mo; annual: propose ~2 months free, e.g. ~€199/yr — validate, don't hard-code)
Higher preparation/practice limits; richer/full History; enhanced Progress; expanded memory;
current-market research; private documents + CV analysis; evidence/story bank; enhanced reports/export;
recorded Practice; realtime voice where available; Advanced model access; higher provider-backed limits.

### Entitlement analysis (per capability)
For each Premium capability, P1/E1 records: user value · marginal provider/storage cost · abuse risk ·
privacy impact · enforcement point · server-side requirement · Basic fallback · acceptance test. No
restriction relies on hiding a frontend control.

### Always-free (trust/safety) — never Premium-gated
Account security, login/logout/session, privacy info, export my data, delete my data/account, memory
management, document/recording deletion, sharing revocation, AI-limitation transparency, citations/
provenance honesty, safe failure. Teams/collaboration is a **separate entitlement dimension**, not
auto-bundled into Premium.

## Admin Console (D1)
Current state: **ABSENT** (reviewer/diagnostics + Settings are NOT an admin control plane).
Target (PLATFORM_ADMIN only, server-side authz, audited, least-privilege):
account overview/status, platform-role + entitlement assignment, workspace/membership overview,
feature flags, usage/operational metrics, system/knowledge/eval readiness status, provider config
**status** (never secret values), model/profile availability, retention/deletion ops, privacy-request
handling, audit-event view, safe platform configuration.
**Never exposed:** secrets/tokens/passwords, CoT, raw prompts, other users' CVs/answers/private memory.
Personal records stay private even from admins unless explicitly justified, least-privilege and audited.
Phasing: role/RBAC + audit + entitlement foundation (P1) → operational console (P6) → prod hardening +
rate limits + route protection (P8). No unrestricted superuser bypass.

## Multi-agent decision
**Current:** one bounded ReAct/goal-based LangGraph agent (Mo) — genuine goal, typed `AgentState`,
reason/act loop with allowlisted tools, observations, bounded step budget + stopping, HITL for side
effects, deterministic tools for facts/calculations. This already satisfies the goal-based-agent
requirement.
**Recommendation:** adopt a **bounded orchestrator/specialist** pattern in P5 **only** for genuinely
independent objectives — Research, Candidate, Preparation, Evaluation specialists under Mo — with:
1) independent goal per specialist; 2) justified as agent vs tool only where autonomous reasoning
adds value; 3) allowlisted tools; 4) read-scoped state; 5) narrow write scope via typed hand-off;
6) explicit stopping/budget; 7) typed hand-off to the supervisor; 8) safety boundary (no auth/
permissions/migrations/billing/self-modification); 9) independent evaluation; 10) safe failure/
cancellation. Keep a single-agent/single-profile **baseline** for measured comparison. Deterministic
Practice retains session authority. Do **not** convert deterministic subsystems into agents for
terminology. **Not implemented in P0/E0.**

## Marketing website (D7)
Current: **ABSENT** (`/` is the product home). Target: public front door in the same Next.js
deployment via a `(marketing)` route group — Home, How It Works, Interview Practice, Career
Intelligence, Mo, Pricing, Trust & Privacy, Help, About, Sign In, Get Started. Communicates target
user/problem/value, evidence approach, journey, privacy/trust, Basic/Premium, AI limitations, CTA to
register. Responsive, accessible, SEO/OG metadata, legal links. No reviewer/diagnostics as marketing;
no unvalidated live-capability claims. Prefer single deployment (public + authenticated route groups)
unless a concrete security/deploy reason forces separation. Implemented in P8.

## Commercial model summary
Basic (€0) vs Premium (hypothesis €19.99/mo). Cost drivers: LLM tokens, STT/TTS minutes, OCR,
storage, email. Billing/checkout **out of scope**; entitlements are data-driven and future-billing-ready.
