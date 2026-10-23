"""07A (PG-10, REQ-DEFER-01): the ONE data table of every DEFERRED or GATED feature family.

Everything the inaccessibility suite checks is derived from this table: the code-defined gate constants, the API routes that must stay refused or inert (with the documented
status for each persona), the route prefixes and keywords that fail the route-inventory guard when a new route appears unlisted, the UI paths and visible texts that must be absent,
and the frontend sources that must never reference the feature. The frontend tests read a generated JSON mirror (``frontend/tests/fixtures/deferral-table-07a.json``, regenerated
with ``python -m tests._deferral_table_07a --write``) so the Python table stays the only source.

Nothing here enables, builds or weakens a feature, and no gate value is changed: a family is inaccessible only while its constants are False.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "/api/v1"
MIRROR = ROOT / "frontend/tests/fixtures/deferral-table-07a.json"

ANON, CAND, SUPPORT, BILLING, PLATFORM = "anonymous", "candidate", "support_operator", "billing_admin", "platform_admin"
PERSONAS = (ANON, CAND, SUPPORT, BILLING, PLATFORM)
AUTHED = (CAND, SUPPORT, BILLING, PLATFORM)


def everyone(status: int, anon: int | None = None) -> dict[str, int]:
    """The same documented status for every authenticated persona; ``anon`` is the unauthenticated (production, fail-closed) answer."""
    return {ANON: anon if anon is not None else status, **{p: status for p in AUTHED}}


def admin_only(permitted: tuple[str, ...], status: int) -> dict[str, int]:
    """401 for anonymous, 403 for everybody not holding the permission, ``status`` for those who do."""
    return {ANON: 401, **{p: (status if p in permitted else 403) for p in AUTHED}}


@dataclass(frozen=True)
class Route:
    method: str
    path: str                                   # relative to /api/v1
    expect: dict                                # persona -> HTTP status
    kind: str                                   # refused | inert | governance | mock_admin
    body: dict | None = None
    headers: dict = field(default_factory=dict)
    upload: bool = False                        # multipart audio upload (speech transcription)
    code: str | None = None                     # stable error code the refusal must carry
    code_personas: tuple = AUTHED               # personas the code applies to (a lower persona may be refused earlier with a different code)
    text_absent: tuple[str, ...] = ()           # regexes that must not appear in any response body (no leak, no provider data)
    json_equals: dict | None = None             # keys that must equal these values in a 200 body


@dataclass(frozen=True)
class Family:
    id: str
    title: str
    release: str
    gates: tuple[tuple[str, str], ...]          # (module, constant): every one must be False
    gate_note: str
    routes: tuple[Route, ...]
    forbidden_prefixes: tuple[str, ...] = ()    # no route may exist under these at all (family has no API by design)
    ui_absent_paths: tuple[str, ...] = ()       # candidate UI paths that must not exist (direct URL navigation answers the not-found page)
    ui_absent_texts: tuple[str, ...] = ()       # regexes that must not appear in the candidate More menu, primary navigation or Admin navigation
    ui_known_routes: tuple[str, ...] = ()       # UI routes that exist under a gated keyword and are inert while the gate is off (the UI-route guard fails on any other)
    no_import_modules: tuple[str, ...] = ()     # src modules that no candidate-facing code may import
    deployment_note: str = ""


_CHECKOUT_LEAK = (r"checkout\.stripe\.com", r"cs_(test|live)_", r"sk_(test|live)_", r"whsec_", r"redirect_url\"\s*:\s*\"https")
_PROVIDER_LEAK = (r"sk_(test|live)_", r"whsec_", r"api[_-]?key", r"Bearer\s+[A-Za-z0-9]", r"Traceback")


def _admin_get(path: str, permitted: tuple[str, ...] = (BILLING, PLATFORM), status: int = 200) -> Route:
    return Route("GET", path, admin_only(permitted, status), "mock_admin" if not path.startswith("/admin/billing/operations") else "inert", text_absent=_PROVIDER_LEAK)


FAMILIES: tuple[Family, ...] = (
    Family(
        id="billing_checkout", title="Live billing: Stripe checkout, paid plans (candidate side)", release="R1.1",
        gates=(("src.billing.policy", "LIVE_BILLING_ENABLED"), ("src.billing.policy", "EXTERNAL_CHECKOUT_AUTHORIZED"), ("src.billing.policy", "PAID_ENTITLEMENT_POLICY_APPROVED")),
        gate_note="Code constants: no setting, startup or Admin action turns them on; checkout is refused 503 for every persona and no Stripe client is built.",
        routes=(
            Route("GET", "/billing/checkout/availability?plan=premium", everyone(200), "inert", json_equals={"available": False, "reason": "not_enabled"}, text_absent=_CHECKOUT_LEAK),
            Route("POST", "/billing/checkout-sessions", everyone(503, anon=401), "refused", body={"plan": "premium"}, headers={"Idempotency-Key": "deferral07a-0001"}, text_absent=_CHECKOUT_LEAK),
            Route("POST", "/billing/checkout-returns", everyone(404, anon=401), "refused", body={"checkout_id": "deferral07a-unknown", "outcome": "success"}, code="not_found", text_absent=_CHECKOUT_LEAK),
            Route("GET", "/billing/checkout/status", everyone(200, anon=401), "inert", json_equals={"checkout": "none", "subscription": "none", "payment": "none"}, text_absent=_CHECKOUT_LEAK),
            Route("GET", "/billing/summary", everyone(200, anon=401), "inert", json_equals={"state": "free", "subscription": "none", "payment": "none"}, text_absent=_CHECKOUT_LEAK),
        ),
        ui_absent_paths=("/checkout", "/billing/checkout", "/billing/portal", "/subscribe", "/upgrade", "/payment", "/payments", "/invoices", "/stripe"),
        ui_absent_texts=(r"\bcheckout\b", r"\bstripe\b", r"subscribe", r"upgrade (now|to premium)", r"buy (premium|now)", r"pay (now|with)"),
        ui_known_routes=("/billing/return", "/pricing", "/account"),
    ),
    Family(
        id="stripe_webhook", title="Stripe webhook processing", release="R1.1",
        gates=(("src.billing.policy", "STRIPE_WEBHOOK_AUTHORIZED"),),
        gate_note="Code constant: the signed-webhook route refuses every request 503 before reading a secret, verifying a signature or storing an event.",
        routes=(
            Route("POST", "/billing/webhooks/stripe", everyone(503), "refused", text_absent=_PROVIDER_LEAK + (r"evt_",)),
        ),
    ),
    Family(
        id="mail_delivery_webhook", title="Mail delivery-event webhook (Brevo)", release="with OD-HOSTED / identity live verification (05D)",
        gates=(("src.mail.webhook", "DELIVERY_EVENTS_AUTHORIZED"),),
        gate_note="Code constant: the signed-webhook route refuses every request 503 before reading a secret, verifying a signature or storing an event; acceptance is never delivery.",
        routes=(
            Route("POST", "/mail/webhooks/brevo", everyone(503), "refused", text_absent=_PROVIDER_LEAK),
        ),
    ),
    Family(
        id="billing_reconciliation", title="Provider reads, reconciliation and the reconciliation scheduler", release="R1.1",
        gates=(("src.billing.policy", "PROVIDER_READS_AUTHORIZED"), ("src.billing.policy", "RECONCILE_SCHEDULER_ENABLED")),
        gate_note="Code constants: the runtime reader is the Null reader; every recovery action is refused reader_unavailable; the scheduler tick enqueues nothing.",
        routes=(
            _admin_get("/admin/billing"), _admin_get("/admin/billing/terms"), _admin_get("/admin/billing/approvals"), _admin_get("/admin/billing/invoices"),
            _admin_get("/admin/billing/payments"), _admin_get("/admin/billing/refunds"), _admin_get("/admin/billing/customers"),
            Route("GET", "/admin/billing/invoices/deferral07a-unknown", admin_only((BILLING, PLATFORM), 404), "mock_admin", text_absent=_PROVIDER_LEAK),
            Route("GET", "/admin/billing/payments/deferral07a-unknown", admin_only((BILLING, PLATFORM), 404), "mock_admin", text_absent=_PROVIDER_LEAK),
            Route("POST", "/admin/billing/price-changes", admin_only((BILLING, PLATFORM), 422), "mock_admin", body={}),
            Route("POST", "/admin/billing/price-changes/deferral07a-unknown/approve", admin_only((BILLING, PLATFORM), 404), "mock_admin", body={}),
            Route("POST", "/admin/billing/price-changes/deferral07a-unknown/reject", admin_only((BILLING, PLATFORM), 404), "mock_admin", body={}),
            Route("POST", "/admin/billing/payments/deferral07a-unknown/refunds", admin_only((BILLING, PLATFORM), 422), "mock_admin", body={}),
            Route("POST", "/admin/billing/refunds/deferral07a-unknown/approve", admin_only((BILLING, PLATFORM), 404), "mock_admin", body={}),
            Route("POST", "/admin/billing/refunds/deferral07a-unknown/reject", admin_only((BILLING, PLATFORM), 404), "mock_admin", body={}),
            _admin_get("/admin/billing/operations/overview"), _admin_get("/admin/billing/operations/readiness"), _admin_get("/admin/billing/operations/subscriptions"),
            _admin_get("/admin/billing/operations/checkouts"), _admin_get("/admin/billing/operations/events"), _admin_get("/admin/billing/operations/reconciliation"),
            _admin_get("/admin/billing/operations/recovery-actions"),
            Route("GET", "/admin/billing/operations/events/deferral07a-unknown", admin_only((BILLING, PLATFORM), 404), "inert", text_absent=_PROVIDER_LEAK),
            Route("GET", "/admin/billing/operations/step-up", admin_only((BILLING, PLATFORM), 200), "inert"),
            Route("POST", "/admin/billing/operations/step-up", admin_only((BILLING, PLATFORM), 403), "inert", body={"password": "not-the-password-07a"}),
            Route("POST", "/admin/billing/operations/events/deferral07a-unknown/retry", admin_only((BILLING, PLATFORM), 403), "refused", body={"reason": "operator retry 07a"},
                  headers={"Idempotency-Key": "deferral07a-0002"}, code="step_up_required", code_personas=(BILLING, PLATFORM)),
            Route("POST", "/admin/billing/operations/events/deferral07a-unknown/requeue", admin_only((BILLING, PLATFORM), 403), "refused", body={"reason": "operator retry 07a"},
                  headers={"Idempotency-Key": "deferral07a-0003"}, code="step_up_required", code_personas=(BILLING, PLATFORM)),
            Route("POST", "/admin/billing/operations/subscriptions/deferral07a-unknown/reconcile", admin_only((BILLING, PLATFORM), 403), "refused", body={"reason": "operator retry 07a"},
                  headers={"Idempotency-Key": "deferral07a-0004"}, code="step_up_required", code_personas=(BILLING, PLATFORM)),
        ),
        ui_absent_texts=(r"go live", r"enable live billing", r"live payments? (are )?(on|enabled)", r"revenue", r"\bMRR\b"),
        ui_known_routes=("/admin/billing",),
    ),
    Family(
        id="speech_server", title="Server-side speech (STT, TTS) and voice cloning", release="R1.4",
        gates=(("src.speech.policy", "SERVER_SPEECH_PROVIDERS_AUTHORIZED"), ("src.speech.policy", "WHISPER_API_TRANSPORT_AUTHORIZED"), ("src.speech.policy", "MODEL_DOWNLOADS_AUTHORIZED"),
               ("src.speech.policy", "VOICE_CLONING_ENABLED")),
        gate_note="Code constants: transcription and synthesis answer 503 speech_unavailable for every persona; no engine runs, no model is downloaded, no audio leaves the process.",
        routes=(
            Route("GET", "/speech/capabilities", everyone(200, anon=401), "inert", json_equals={"server_stt_languages": [], "server_tts_languages": [], "audio_persisted": False}),
            Route("POST", "/speech/transcriptions", everyone(503, anon=401), "refused", upload=True, code="speech_unavailable", text_absent=_PROVIDER_LEAK),
            Route("POST", "/speech/synthesis", everyone(503, anon=401), "refused", body={"text": "Hello there from the deferral suite.", "language": "en"}, code="speech_unavailable", text_absent=_PROVIDER_LEAK),
            Route("GET", "/admin/speech", admin_only((PLATFORM,), 200), "governance"),
            Route("PUT", "/admin/speech", admin_only((PLATFORM,), 422), "governance", body={}),
        ),
        ui_absent_paths=("/speech", "/transcribe", "/voice-practice", "/admin/speech/providers", "/admin/speech/enable"),
        ui_absent_texts=(r"server[- ]side (speech|transcription)", r"whisper", r"kyutai", r"clone (your )?voice", r"voice cloning"),
        ui_known_routes=("/admin/speech",),
    ),
    Family(
        id="realtime_voice", title="Realtime (live) voice practice", release="R1.4",
        gates=(),
        gate_note="Gated by deployment configuration (REALTIME_VOICE_ENABLED plus REALTIME_VOICE_API_KEY), NOT by a code constant: with neither set it answers 503 with the turn-based fallback. "
                  "See the 07A evidence file: this is a gap the owner should decide on.",
        routes=(
            Route("GET", "/voice/realtime/status", everyone(200, anon=401), "inert", json_equals={"enabled": False, "available": False, "configured": False, "fallback": "turn_based_voice"}),
            Route("POST", "/voice/realtime/session", everyone(503, anon=401), "refused", body={"locale": "en", "surface": "practice"}, text_absent=_PROVIDER_LEAK + (r"ephemeral", r"client_secret")),
            Route("POST", "/voice/realtime/session/end", everyone(200, anon=401), "inert", json_equals={"status": "ended"}),
        ),
        ui_absent_paths=("/live-voice", "/voice", "/realtime", "/practice/live"),
        ui_absent_texts=(r"start live voice", r"live voice", r"realtime voice"),
        deployment_note="realtime_voice_enabled is false in /capabilities unless the deployment flag, a provider key and the durable pause all allow it.",
    ),
    Family(
        id="compensation_v2", title="Compensation Intelligence V2", release="R1.6",
        gates=(),
        gate_note="Not operational: knowledge_foundation readiness reports operational_today False, 0 linkable V2 records and 0 approved V2 sources; no API route, UI route or candidate-facing "
                  "import exists, and nothing may be added under the forbidden prefixes.",
        routes=(),
        forbidden_prefixes=("/compensation", "/compensation-v2", "/salary", "/salaries", "/pay-data", "/admin/compensation"),
        ui_absent_paths=("/compensation", "/compensation-v2", "/salary", "/salaries", "/admin/compensation"),
        ui_absent_texts=(r"compensation (intelligence )?v2", r"salary (benchmark|explorer|data)", r"pay benchmark"),
        no_import_modules=("src.knowledge_foundation.compensation",),
    ),
    Family(
        id="international_sources", title="International and global sources, additional-country coverage and global provenance", release="R1.5",
        gates=(),
        gate_note="Not operational: no country source is licence-verified or approved (readiness operational_today False for every non-DE country); no API or UI route exists and no "
                  "candidate-facing module imports the global foundation, evaluator or reports.",
        routes=(),
        forbidden_prefixes=("/global", "/international", "/global-sources", "/countries", "/admin/global", "/admin/international", "/admin/sources/global"),
        ui_absent_paths=("/global", "/international", "/global-sources", "/countries", "/admin/global", "/admin/international"),
        ui_absent_texts=(r"global (sources|coverage|provenance)", r"international (sources|coverage|salary)", r"additional countries"),
        no_import_modules=("src.knowledge_foundation.global_eval", "src.knowledge_foundation.global_reports", "src.knowledge_foundation.readiness",
                           "src.knowledge_foundation.us_sources", "src.knowledge_foundation.us_qualification", "src.knowledge_foundation.us_alias_review"),
    ),
    Family(
        id="history_gating", title="Basic history window (gated access limit)", release="with OD-PLAN-ENFORCE",
        gates=(("src.application.history_access", "HISTORY_RESTRICTIONS_ENFORCED"),),
        gate_note="Code constant: while False no completed interview is hidden, restricted or counted as hidden for any persona (the restriction is not live; nothing is ever deleted).",
        routes=(
            Route("GET", "/history/interviews", everyone(200, anon=401), "inert", json_equals={"interviews": []}),
            Route("GET", "/history/interviews/987654321", everyone(404, anon=401), "inert", code="not_found"),
            Route("DELETE", "/history/interviews/987654321", everyone(404, anon=401), "inert", code="not_found"),
        ),
        ui_absent_texts=(r"history (window|limit)", r"latest three", r"only the (latest|last) 3"),
    ),
    Family(
        id="model_profile_gating", title="Plan-gated AI model-profile selection", release="with OD-PLAN-ENFORCE",
        gates=(("src.application.model_profile_access", "MODEL_PROFILE_ENFORCED"),),
        gate_note="Code constant: while False no selector is active (selector_active false), Basic accounts are not moved to Fast and a Practice model_profile other than the default is refused.",
        routes=(
            Route("GET", "/model-profiles", everyone(200, anon=401), "inert", json_equals={"selector_active": False, "default": "balanced"}),
        ),
        ui_absent_texts=(r"model profile", r"choose (a )?model", r"advanced model"),
    ),
)

# Gate constants that exist in code but are NOT in scripts/production/reconcile_issues.py GATE_CONSTANTS (found by the discovery scan). They belong to other deferred or gated
# capabilities, are asserted False here, and the owner/lead may decide to add them to the reconciliation list (07A does not edit that generated-document script).
ADDITIONAL_GATES: dict[tuple[str, str], str] = {
    ("src.ai_protection", "AI_COST_LIMITS_ENFORCED"): "AI cost limits are not enforced (OD-AI-LIMITS)",
    ("src.application.usage_quota", "USAGE_QUOTAS_ENFORCED"): "usage quotas are not enforced",
    ("src.application.preparation_pack", "PREPARATION_PACK_GENERATION_ENABLED"): "preparation-pack generation is disabled",
    ("src.application.progress_analytics", "PREMIUM_ANALYTICS_ENABLED"): "premium analytics are disabled",
}

# A gate-like constant is any module-level NAME = True/False whose name ends in one of these (the discovery scan fails when it finds one that is neither in the reconciliation list,
# the families above nor ADDITIONAL_GATES).
# Safety controls that are deliberately ON (the opposite of a deferral gate). The discovery scan classifies them here and the test pins each one True, so switching one off fails the suite.
SAFETY_CONTROLS_ON: dict[tuple[str, str], str] = {
    ("src.constants", "MULTILINGUAL_INPUT_GUARD_ENABLED"): "06E: the multilingual interview input guard is on (False restores the English-only guard exactly)",
}

GATE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*(_ENFORCED|_AUTHORIZED|_ENABLED|_APPROVED)$|^VOICE_CLONING_ENABLED$")

# The route-inventory guard: any OpenAPI path whose segments contain one of these tokens (or that starts with a gated prefix) must be listed in a family, or the suite fails.
GATED_PATH_TOKENS = frozenset({
    "billing", "stripe", "checkout", "webhook", "webhooks", "speech", "voice", "realtime", "compensation", "international", "global", "reconcile", "reconciliation",
    "stt", "tts", "transcriptions", "synthesis", "subscribe", "payment", "payments", "invoices", "salary", "salaries", "model-profiles", "history",
})
# Admin paths that contain a token only by coincidence and are covered elsewhere (plan administration and the AI audit history are permission-matrix domains, not deferred features).
GATED_PATH_COINCIDENCE = frozenset({"/admin/ai/history", "/privacy/legal/history"})     # the second is the legal-document version history (a privacy read), not the plan-gated history window
GATED_PATH_PREFIXES = ("/billing", "/admin/billing", "/speech", "/admin/speech", "/voice", "/model-profiles", "/history")

# UI routes (Next.js app directory names) that carry a gated keyword. A new directory under any of these keywords fails the UI-route guard unless a family lists it in ui_known_routes.
GATED_UI_KEYWORDS = ("billing", "checkout", "stripe", "payment", "subscribe", "speech", "voice", "realtime", "compensation", "salary", "international", "global", "transcri")


def all_listed_routes() -> set[tuple[str, str]]:
    return {(r.method, r.path.split("?")[0]) for f in FAMILIES for r in f.routes}


def to_json() -> dict:
    """The mirror consumed by the frontend tests: only data the browser-side checks need (no expectations about the API)."""
    return {
        "schema": "deferral_table_07a/1",
        "families": [
            {"id": f.id, "title": f.title, "release": f.release, "gates": [f"{m}.{n}" for m, n in f.gates], "ui_absent_paths": list(f.ui_absent_paths),
             "ui_absent_texts": list(f.ui_absent_texts), "ui_known_routes": list(f.ui_known_routes),
             "api_paths": sorted({f"{API}{r.path.split('?')[0]}" for r in f.routes}), "forbidden_prefixes": list(f.forbidden_prefixes)}
            for f in FAMILIES
        ],
        "gated_ui_keywords": list(GATED_UI_KEYWORDS),
    }


def render_json() -> str:
    return json.dumps(to_json(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":   # pragma: no cover
    import sys

    if "--write" in sys.argv:
        MIRROR.write_text(render_json())
        print(f"wrote {MIRROR}")
    else:
        print(render_json())
