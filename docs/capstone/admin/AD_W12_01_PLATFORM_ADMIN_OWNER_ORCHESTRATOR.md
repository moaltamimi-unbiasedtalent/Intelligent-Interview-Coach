# AD-W12-01 - Platform Admin owner / orchestrator

**Status: DECIDED (owner approved) and IMPLEMENTED in W12.1** (`docs/capstone/admin/W12_01_PLATFORM_ADMIN_OWNER_ORCHESTRATOR_IMPLEMENTATION.md`). The decision was first recorded as forward-looking (not implemented); W12.1 changed the code-defined `platform_admin` preset to 43 / 43. Implementation changed no migration and no registry entry. RC-P10-004 has not been created and the Admin Owner Walkthrough has not started.

## Decision
`platform_admin` will become the platform **owner / orchestrator** role and will hold **all 43 canonical platform permissions (43 / 43)**. Specialist Admin roles (operations, support, billing, security, privacy, knowledge and similar) remain **least-privilege delegated roles**.

## Relationship to W10.14 (history preserved)
The W10.14 qualification decision stands as a truthful record of that point in time: `platform_admin` held **28 of 43** permissions ("broad but not universal", ROLE-W10-01 closed as least-privilege domain separation). That evidence is not rewritten. AD-W12-01 supersedes only the **future-looking** role decision.

## Constraints that remain (unchanged by this decision)
- No unrestricted candidate-content browser unless an explicit, governed capability is separately designed and approved.
- No impersonation ("view as user").
- No break-glass.
- Sensitive actions still require step-up and two-person approval where they are designed that way.
- Audit remains mandatory and append-only.
- No role-name authorization: every privileged route stays `require_permission`-gated.

## Sequencing (as originally recorded)
Implementation was scheduled after Pilot 2 remediation qualification (see the roadmap in `capstone_phase_plan.md`). It changed `src/application/admin_permissions.py` presets and the Admin evidence (the 43 x 7 matrix expectations, W10.14 and W11 evaluators, `CLAUDE.md`), and, because it changes authorization behaviour, is expected to require a new RC (RC-P10-004). The **Admin Owner Walkthrough** is scheduled only after Pilot 2 remediation and after this owner-role change.
