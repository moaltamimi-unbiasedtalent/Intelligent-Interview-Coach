"""Admin capability readiness (W12.4F): one truthful, derived view of what each supported operational capability actually is.

* Reuses the existing sources of truth (integration registry, SecretStore, speech runtime, billing operations, gate constants, pause and flag services). It adds no table, no persistent status
  enum, no provider call and no setting. Every row is derived at request time; a source that cannot be read is reported ``unavailable``, never as healthy.
* Statuses use the canonical W12.4F vocabulary. ``status`` is the primary classification; ``qualifiers`` add the independent facts (OFFLINE_VALIDATED, LIVE_UNVERIFIED, DEFERRED, ...).
  Configuration present is never ``OPERATIONAL``; a mock or fixture passing is never live; credentials present is never ready; a provider acceptance is never delivery.
* Rows are omitted for callers that lack the owning domain's read permission (same rule as the Command Center). No secret, path, audio, candidate content or raw error text is carried.
"""

from __future__ import annotations

from typing import Any, Callable

from src.application import admin_permissions as perm

STATUSES = ("OPERATIONAL", "CONFIGURED_BUT_UNAVAILABLE", "ENVIRONMENT_MANAGED", "MOCK", "READ_ONLY", "PARTIAL", "NOT_BUILT")
QUALIFIERS = ("OFFLINE_VALIDATED", "LIVE_UNVERIFIED", "DEFERRED", "UNAVAILABLE", "DISABLED")

BOUNDARY = ("Derived from the running configuration and recorded evidence. A capability is OPERATIONAL only when it is implemented, authorized and proven usable in its supported environment; "
            "configuration, credentials, a passing mock or an accepted request never make it so. This is not a statement that the platform is production ready.")


def _row(rid: str, label: str, path: str | None, status: str, qualifiers: list[str], ownership: str, evidence: str, limitations: list[str], required: str, basis: str = "runtime") -> dict[str, Any]:
    assert status in STATUSES and all(q in QUALIFIERS for q in qualifiers)
    return {"id": rid, "label": label, "admin_path": path, "status": status, "qualifiers": qualifiers, "ownership": ownership, "basis": basis, "evidence": evidence,
            "limitations": limitations, "_perm": required}


def _unavailable(rid: str, label: str, path: str | None, ownership: str, required: str) -> dict[str, Any]:
    return _row(rid, label, path, "CONFIGURED_BUT_UNAVAILABLE", ["UNAVAILABLE"], ownership, "The authoritative state could not be read right now.", ["Not reported as healthy."], required)


def _guard(rid: str, label: str, path: str | None, ownership: str, required: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - an unreadable source is reported as unavailable, never as healthy, and the error text is not carried
        return _unavailable(rid, label, path, ownership, required)


def capability_readiness(*, allowed: frozenset[str], speech_runtime=None, integrations=None, secret_store=None, billing_ops=None, ai=None, knowledge=None, pause=None, flags=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    # --- access control (code-defined; there is no runtime toggle) -------------------------------------------------------------------------------------
    rows.append(_row("rbac", "Role-based access", "/admin/users", "OPERATIONAL", ["OFFLINE_VALIDATED"], "Platform Admin (code-defined presets)",
                     f"{len(perm.PERMISSIONS)} code-defined permissions; every admin route declares one; default deny.", ["No custom roles; presets are code, not configuration."], perm.OVERVIEW_READ, "code"))

    # --- SecretStore -----------------------------------------------------------------------------------------------------------------------------------
    def secret_row() -> dict[str, Any]:
        st = secret_store.write_state() if hasattr(secret_store, "write_state") else {"state": "writable" if getattr(secret_store, "supports_write", False) else "read_only", "reason": None}
        if st["state"] == "writable":
            return _row("secret_store", "SecretStore", "/admin/integrations", "OPERATIONAL", ["LIVE_UNVERIFIED"], "Platform Admin (write-only, step-up); master key is deployment-managed",
                        "Encrypted writable store active with environment fallback. Secret values are never readable.", ["The master key is supplied by the deployment, not Admin."], perm.INTEGRATIONS_READ)
        if st["state"] == "unavailable":
            return _row("secret_store", "SecretStore", "/admin/integrations", "CONFIGURED_BUT_UNAVAILABLE", ["UNAVAILABLE"], "Deployment infrastructure (master key)",
                        "The encrypted store is selected but not usable (master key state: %s)." % (st.get("reason") or "unknown"), ["Environment fallback applies for reads."], perm.INTEGRATIONS_READ)
        return _row("secret_store", "SecretStore", "/admin/integrations", "ENVIRONMENT_MANAGED", [], "Deployment infrastructure",
                    "Read-only environment adapter: secrets are set in the deployment environment.", ["No secret can be written from Admin."], perm.INTEGRATIONS_READ)

    if secret_store is not None:
        rows.append(_guard("secret_store", "SecretStore", "/admin/integrations", "Deployment infrastructure", perm.INTEGRATIONS_READ, secret_row))

    # --- integrations, email, identity -----------------------------------------------------------------------------------------------------------------
    items: list[dict] = []
    if integrations is not None:
        try:
            items = integrations.list()
        except Exception:  # noqa: BLE001
            rows.append(_unavailable("integrations", "Integrations", "/admin/integrations", "Platform Admin", perm.INTEGRATIONS_READ))
        else:
            healthy = sum(1 for i in items if i["health"]["status"] == "healthy")
            rows.append(_row("integrations", "Integrations registry", "/admin/integrations", "PARTIAL", ["LIVE_UNVERIFIED"] if not healthy else [], "Platform Admin (registry is code-defined; runtime state is environment-managed)",
                             f"{len(items)} registered; {sum(1 for i in items if i['configuration_status'] == 'configured')} configured; {healthy} passed a manual test.",
                             ["Only bounded manual tests exist (no polling); 'configured' is never 'healthy'; no custom integrations."], perm.INTEGRATIONS_READ))
            by = {i["code"]: i for i in items}
            em = by.get("email_brevo")
            if em is not None:
                live = em["classification"] == "runtime_active"
                rows.append(_row("email_delivery", "Transactional email", "/admin/integrations/email_brevo", "PARTIAL" if live else "MOCK",
                                 ["LIVE_UNVERIFIED"], "Deployment environment (provider, key, sender); Admin runs bounded tests",
                                 "Brevo is the active provider." if live else "Console or memory delivery: nothing is sent to a real mailbox.",
                                 ["A provider acceptance is not delivery; live delivery has not been verified by recorded evidence."], perm.INTEGRATIONS_READ))
            oidc = by.get("google_oidc")
            if oidc is not None:
                rows.append(_row("identity_google_oidc", "Google sign-in (OIDC)", "/admin/integrations/google_oidc", "PARTIAL", ["LIVE_UNVERIFIED"], "Deployment environment (client credentials)",
                                 "Backend support present; classification: %s." % oidc["classification"], ["End-to-end sign-in is not validated and is not wired into the candidate sign-in page."], perm.INTEGRATIONS_READ))

    # --- AI models -------------------------------------------------------------------------------------------------------------------------------------
    if ai is not None:
        def ai_row() -> dict[str, Any]:
            s = ai.stats()
            return _row("ai_models", "AI model governance", "/admin/ai", "PARTIAL", ["OFFLINE_VALIDATED", "LIVE_UNVERIFIED"], "Platform Admin (governed profiles); provider keys and pricing are environment-managed",
                        f"{s.get('versions', 0)} configuration versions; {s.get('pending_approvals', 0)} pending approvals.", ["Deterministic evaluation only: no live model call was made to qualify a configuration.", "No arbitrary model name or endpoint can be entered."], perm.AI_READ)
        rows.append(_guard("ai_models", "AI model governance", "/admin/ai", "Platform Admin", perm.AI_READ, ai_row))

    # --- knowledge -------------------------------------------------------------------------------------------------------------------------------------
    if knowledge is not None:
        def kb_row() -> dict[str, Any]:
            s = knowledge.stats()
            return _row("knowledge", "Knowledge sources", "/admin/knowledge", "PARTIAL", ["OFFLINE_VALIDATED", "DEFERRED"], "Knowledge Admin (governed workflow); source qualification is a source-governance workflow",
                        f"{s.get('sources', 0)} governed sources; {s.get('active', 0)} active versions; {s.get('awaiting_review', 0)} awaiting review.",
                        ["Remaining source acquisition, licensing and human evidence review (P10C-F) are deferred until after capstone submission.", "Compensation V2 is disabled."], perm.KNOWLEDGE_READ)
        rows.append(_guard("knowledge", "Knowledge sources", "/admin/knowledge", "Knowledge Admin", perm.KNOWLEDGE_READ, kb_row))

    # --- speech ----------------------------------------------------------------------------------------------------------------------------------------
    if speech_runtime is not None:
        def speech_rows() -> list[dict[str, Any]]:
            r = speech_runtime.readiness()
            out = []
            for key, label, engine_name in (("stt", "Server speech to text (Whisper)", "openai_whisper"), ("tts", "Server text to speech (Kyutai Pocket TTS)", "kyutai_pocket_tts")):
                x = r[key]
                q = ["OFFLINE_VALIDATED"] if x["validated_with_fixture"] else []
                q += ["LIVE_UNVERIFIED", "DEFERRED"]
                if not x["configured"]:
                    q.append("DISABLED")
                out.append(_row(f"speech_{key}", label, "/admin/speech", "OPERATIONAL" if x["operational"] else "CONFIGURED_BUT_UNAVAILABLE" if x["configured"] else "PARTIAL", q,
                                "Platform Admin selects provider and policy; activation needs code authorization (owner decision)",
                                f"{engine_name}: adapter contract validated with a fixture; genuine model execution {x['validated_with_genuine_model']}; operational={x['operational']}.",
                                ["Activation, licensing and live validation are deferred until after capstone submission.", "Dutch server TTS is unverified; Russian speech is excluded."] if key == "tts" else
                                ["Activation, hosting decisions and live validation are deferred until after capstone submission.", "Russian speech is excluded."], perm.FLAGS_READ))
            return out
        try:
            rows.extend(speech_rows())
        except Exception:  # noqa: BLE001
            rows.append(_unavailable("speech", "Server speech", "/admin/speech", "Platform Admin", perm.FLAGS_READ))

    # --- billing ---------------------------------------------------------------------------------------------------------------------------------------
    if billing_ops is not None:
        def billing_row() -> dict[str, Any]:
            r = billing_ops.readiness()
            live = r.get("live_billing") == "enabled"
            return _row("billing", "Billing", "/admin/billing", "OPERATIONAL" if live else "MOCK", ["OFFLINE_VALIDATED", "LIVE_UNVERIFIED"] if not live else ["LIVE_UNVERIFIED"],
                        "Commercial activation workflow (owner); Admin shows state only",
                        f"Provider selected: {r.get('provider_selected')}; checkout {r.get('checkout')}; webhook {r.get('webhook')}; live billing {r.get('live_billing')}.",
                        ["Simulated billing: no payment provider is contacted and no real money moves.", "Commercial activation is outstanding."], perm.BILLING_READ)
        rows.append(_guard("billing", "Billing", "/admin/billing", "Commercial activation workflow", perm.BILLING_READ, billing_row))

    # --- durable controls ------------------------------------------------------------------------------------------------------------------------------
    if pause is not None:
        from src.application.admin_command_center import pause_state
        ps = pause_state(pause)
        if ps["status"] == "unavailable":
            rows.append(_unavailable("platform_pause", "Platform pause switches", "/admin/configuration", "Platform Admin", perm.FLAGS_READ))
        else:
            rows.append(_row("platform_pause", "Platform pause switches", "/admin/configuration", "OPERATIONAL", ["OFFLINE_VALIDATED"], "Platform Admin", "Durable per-environment state with revision and same-transaction audit; currently %s." % ps["status"], [], perm.FLAGS_READ))
    if flags is not None:
        def flag_row() -> dict[str, Any]:
            flags.stats()
            return _row("feature_flags", "Feature flags", "/admin/flags", "OPERATIONAL", ["OFFLINE_VALIDATED"], "Platform Admin (code-defined flags, durable overrides)", "Durable overrides readable; baseline retained.", [], perm.FLAGS_READ)
        rows.append(_guard("feature_flags", "Feature flags", "/admin/flags", "Platform Admin", perm.FLAGS_READ, flag_row))

    # --- the twelve rollout and billing gates (code constants: read-only by design) --------------------------------------------------------------------
    def gates_row() -> dict[str, Any]:
        from src.copilot.knowledge.requalification import gate_values
        g = gate_values()
        off = sum(1 for v in g.values() if not v)
        return _row("rollout_gates", "Rollout and billing gates", None, "READ_ONLY", ["DISABLED"] if off == len(g) else [], "Owner authorization (code constants; no Admin control exists by design)",
                    f"{off} of {len(g)} gates are False.", ["Changing a gate requires a reviewed code change."], perm.OVERVIEW_READ, "code")
    rows.append(_guard("rollout_gates", "Rollout and billing gates", None, "Owner authorization", perm.OVERVIEW_READ, gates_row))

    visible = [{k: v for k, v in r.items() if k != "_perm"} for r in rows if r["_perm"] in allowed]
    summary: dict[str, int] = {}
    for r in visible:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    return {"capabilities": visible, "summary": summary, "vocabulary": {"statuses": list(STATUSES), "qualifiers": list(QUALIFIERS)}, "boundary": BOUNDARY}
