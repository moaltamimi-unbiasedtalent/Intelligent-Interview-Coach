"""Integration registry, safe status model and manual connection tests (P10B-W10.6).

* The registry is CODE-defined: Admin cannot create an integration, a provider name, an endpoint or a secret
  field. Every external destination used by a probe is a constant owned by the adapter, so there is no
  user-controlled URL and therefore no SSRF surface.
* Credentials are read only through the ``SecretStore`` for metadata (configured yes/no and source). No value,
  prefix, suffix or mask ever leaves this module.
* Status is deliberately split: ``configuration`` (are credentials present), ``runtime`` (is the feature on,
  as owned by the environment) and ``health`` (only an explicit manual test can make it ``healthy``). Supported
  does not mean connected, configured does not mean healthy.
* Probes run ONLY on an explicit Admin action: bounded timeout, adapter-defined destination, no redirect
  following, no retry, and their result is reduced to a bounded category. No page render, no polling, no job.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.admin_repository import _stage
from src.persistence import INTEGRATION_TEST_CATEGORIES, IntegrationState, utcnow
from src.secret_store import SecretStore, SecretStoreReadOnly, get_secret_store  # noqa: F401  (re-export)

PROBE_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CredentialSlot:
    slot: str            # stable identifier used by the API
    label: str
    external_name: str   # the environment variable NAME the operator manages (a name, never a value)


@dataclass(frozen=True)
class SettingDef:
    code: str
    label: str
    env_name: str
    allowed: tuple[str, ...]   # only these values are ever displayed; anything else is shown as "other"


@dataclass(frozen=True)
class IntegrationDef:
    code: str
    name: str
    category: str
    adapter: str
    description: str
    credentials: tuple[CredentialSlot, ...] = ()
    settings: tuple[SettingDef, ...] = ()
    enabled_flag: str | None = None      # environment flag that turns the feature on (read-only here)
    test_supported: bool = False
    test_note: str = "No safe manual probe exists for this integration."
    validation_note: str = "Not validated against the live provider."


CATEGORIES = {
    "ai_model": "AI / model",
    "career_data": "Labour-market data",
    "authentication": "Authentication",
    "communications": "Email / communications",
    "rate_limiting": "Rate limiting",
    "observability": "Observability",
    "file_security": "File security",
}

REGISTRY: dict[str, IntegrationDef] = {d.code: d for d in (
    IntegrationDef(
        "openrouter", "OpenRouter (language models)", "ai_model", "OpenRouter chat API",
        "Chat model provider for Mo, interview generation and evaluation.",
        credentials=(CredentialSlot("api_key", "API key", "OPENROUTER_API_KEY"),),
        test_supported=True,
        test_note="Calls OpenRouter's key-information endpoint once. It does not run a model and has no usage cost.",
        validation_note="Healthy only after a successful manual test."),
    IntegrationDef(
        "openai_embeddings", "OpenAI embeddings (optional)", "ai_model", "OpenAI embeddings",
        "Optional embedding provider for retrieval. The offline local embedder is the default.",
        credentials=(CredentialSlot("api_key", "Embedding API key", "COPILOT_EMBEDDING_API_KEY"),),
        settings=(SettingDef("provider", "Embedding provider", "COPILOT_EMBEDDING_PROVIDER", ("auto", "local", "openai")),)),
    IntegrationDef(
        "realtime_voice", "Realtime voice provider", "ai_model", "OpenAI Realtime",
        "Optional live spoken exchange with Mo. Off by default; live provider validation has not been run.",
        credentials=(CredentialSlot("api_key", "Realtime API key", "REALTIME_VOICE_API_KEY"),),
        enabled_flag="REALTIME_VOICE_ENABLED",
        settings=(SettingDef("provider", "Provider", "REALTIME_VOICE_PROVIDER", ("openai_realtime",)),),
        validation_note="Live validation NOT RUN."),
    IntegrationDef(
        "adzuna", "Adzuna (job market data)", "career_data", "Adzuna API",
        "Current-market job data for company and role research.",
        credentials=(CredentialSlot("app_id", "Application id", "ADZUNA_APP_ID"),
                     CredentialSlot("app_key", "Application key", "ADZUNA_APP_KEY")),
        test_note="No manual probe: calls consume the provider's quota and live validation is cost-gated.",
        validation_note="Live validation is cost-gated and UNVALIDATED."),
    IntegrationDef(
        "google_oidc", "Google sign-in (OIDC)", "authentication", "Google OpenID Connect",
        "Backend support for Google sign-in. Off by default; end-to-end sign-in is not validated.",
        credentials=(CredentialSlot("client_id", "Client id", "GOOGLE_CLIENT_ID"),
                     CredentialSlot("client_secret", "Client secret", "GOOGLE_CLIENT_SECRET")),
        enabled_flag="FEATURE_GOOGLE_LOGIN",
        test_note="No manual probe: the flow needs an interactive browser sign-in.",
        validation_note="Backend support present; end-to-end sign-in is not validated and is not wired into the candidate sign-in page."),
    IntegrationDef(
        "email_brevo", "Brevo (transactional email)", "communications", "Brevo email API",
        "Sends account emails (verification and password reset) when selected. Support notifications are not sent.",
        credentials=(CredentialSlot("api_key", "API key", "BREVO_API_KEY"),),
        settings=(SettingDef("provider", "Email provider", "EMAIL_PROVIDER", ("console", "brevo", "memory")),),
        test_note="No manual probe: a real test would send an email.",
        validation_note="Live delivery has not been validated; support ticket replies are never emailed."),
    IntegrationDef(
        "redis_rate_limit", "Redis (shared rate limiting)", "rate_limiting", "Redis sliding window",
        "Optional shared store for rate limits across replicas. In-memory per-process limiting is the default.",
        credentials=(CredentialSlot("url", "Connection URL (contains credentials)", "REDIS_URL"),),
        settings=(SettingDef("backend", "Requested backend", "RATE_LIMIT_BACKEND", ("in_memory", "redis", "shared")),),
        validation_note="Tested against a fake client only: distributed limiting is NOT LIVE."),
    IntegrationDef(
        "langfuse", "Langfuse (observability)", "observability", "Langfuse events",
        "Optional external observability of sanitised agent events. Off by default.",
        credentials=(CredentialSlot("public_key", "Public key", "LANGFUSE_PUBLIC_KEY"),
                     CredentialSlot("secret_key", "Secret key", "LANGFUSE_SECRET_KEY")),
        enabled_flag="AGENT_EXTERNAL_OBSERVABILITY_ENABLED"),
    IntegrationDef(
        "malware_scanner", "ClamAV (upload malware scanning)", "file_security", "ClamAV daemon",
        "Optional malware scan of uploaded documents. No credentials are involved.",
        settings=(SettingDef("provider", "Scanner provider", "FILE_SCAN_PROVIDER", ("clamav", "fake")),),
        test_supported=True,
        test_note="Checks that the configured scanner daemon answers. No file is scanned.",
        validation_note="Live scanner validation not run."),
)}


# ------------------------------------------------------------------------------------------------------------
# Runtime-owned state (read from the same configuration the application reads; never mutable from Admin)
# ------------------------------------------------------------------------------------------------------------

def _flag(name: str | None) -> bool | None:
    if not name:
        return None
    from src.core import secrets as rt

    return rt.read_bool(name, default=False)


def _setting(defn: SettingDef) -> str | None:
    from src.core import secrets as rt

    raw = (rt.read_setting(defn.env_name) or "").strip().lower()
    if not raw:
        return None
    return raw if raw in defn.allowed else "other"


def _runtime(defn: IntegrationDef, configured: dict[str, bool], settings: dict[str, str | None]) -> tuple[bool | None, str]:
    """(enabled, classification). Classification is one of runtime_active, configured_inactive,
    supported_unconfigured, code_present_not_validated, development_only. ``Supported`` never becomes ``connected``."""
    all_set = all(configured.values()) if configured else False
    any_set = any(configured.values())
    code = defn.code
    if code == "google_oidc":
        return bool(_flag(defn.enabled_flag) and all_set), "code_present_not_validated"
    if code == "redis_rate_limit":
        try:
            from src.api.rate_limit import shared_store_active
            active = bool(shared_store_active())
        except Exception:  # noqa: BLE001
            active = False
        if active:
            return True, "runtime_active"
        return False, "configured_inactive" if any_set else "supported_unconfigured"
    if code == "malware_scanner":
        prov = settings.get("provider")
        if prov == "fake":
            return True, "development_only"
        return prov == "clamav", "runtime_active" if prov == "clamav" else "supported_unconfigured"
    if code == "email_brevo":
        on = settings.get("provider") == "brevo" and all_set
        return on, "runtime_active" if on else ("configured_inactive" if any_set else "supported_unconfigured")
    if code == "openai_embeddings":
        prov = settings.get("provider")
        on = all_set and prov != "local"
        return on, "runtime_active" if on else ("configured_inactive" if any_set else "supported_unconfigured")
    flag = _flag(defn.enabled_flag)
    if flag is not None:   # realtime_voice, langfuse
        if all_set and flag:
            return True, "runtime_active"
        return False, "configured_inactive" if any_set else "supported_unconfigured"
    return all_set, "runtime_active" if all_set else "supported_unconfigured"   # openrouter, adzuna


def _configuration_status(configured: dict[str, bool], defn: IntegrationDef, settings: dict[str, str | None]) -> str:
    if not defn.credentials:
        return "configured" if any(v for v in settings.values()) else "unconfigured"
    n = sum(configured.values())
    return "configured" if n == len(configured) else ("partially_configured" if n else "unconfigured")


# ------------------------------------------------------------------------------------------------------------
# Probes (explicit, manual, bounded, adapter-defined destination)
# ------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbeResult:
    outcome: str            # success | failure
    category: str           # one of INTEGRATION_TEST_CATEGORIES
    latency_ms: int | None = None


OPENROUTER_PROBE_URL = "https://openrouter.ai/api/v1/auth/key"   # adapter constant: never user input


def probe_openrouter(store: SecretStore, *, transport: httpx.BaseTransport | None = None) -> ProbeResult:
    key = store.get_for_runtime("OPENROUTER_API_KEY")
    if key is None:
        return ProbeResult("failure", "configuration_error")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=PROBE_TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
            resp = client.get(OPENROUTER_PROBE_URL, headers={"Authorization": f"Bearer {key.get_secret_value()}"})
    except httpx.TimeoutException:
        return ProbeResult("failure", "timeout")
    except httpx.HTTPError:
        return ProbeResult("failure", "unavailable")
    ms = int((time.monotonic() - started) * 1000)
    code = resp.status_code
    if 200 <= code < 300:
        return ProbeResult("success", "ok", ms)
    if code in (401, 403):
        return ProbeResult("failure", "unauthorized", ms)
    if code == 429:
        return ProbeResult("failure", "rate_limited", ms)
    if code >= 500:
        return ProbeResult("failure", "unavailable", ms)
    return ProbeResult("failure", "unknown", ms)   # the response body is never read, stored or returned


def probe_malware_scanner(store: SecretStore) -> ProbeResult:
    from src.documents.file_security import build_file_scanner

    if (_setting(SettingDef("provider", "", "FILE_SCAN_PROVIDER", ("clamav", "fake"))) or "") != "clamav":
        return ProbeResult("failure", "configuration_error")
    started = time.monotonic()
    try:
        ok = build_file_scanner().available()
    except Exception:  # noqa: BLE001
        return ProbeResult("failure", "unavailable")
    return ProbeResult("success" if ok else "failure", "ok" if ok else "unavailable", int((time.monotonic() - started) * 1000))


PROBES: dict[str, Callable[[SecretStore], ProbeResult]] = {
    "openrouter": probe_openrouter,
    "malware_scanner": probe_malware_scanner,
}


def run_probe(code: str, store: SecretStore, probes: dict[str, Callable[[SecretStore], ProbeResult]] | None = None) -> ProbeResult:
    """Run the adapter probe and reduce ANY outcome (including an exception, whose text may embed a credential)
    to a bounded category. Exception text is discarded."""
    probe = (probes or PROBES).get(code)
    if probe is None:
        raise KeyError(code)
    try:
        r = probe(store)
    except Exception:  # noqa: BLE001 - never surface exception text
        return ProbeResult("failure", "unknown")
    outcome = "success" if (r.outcome == "success" and r.category == "ok") else "failure"
    category = "ok" if outcome == "success" else (r.category if r.category in INTEGRATION_TEST_CATEGORIES and r.category != "ok" else "unknown")
    latency = r.latency_ms if isinstance(r.latency_ms, int) and 0 <= r.latency_ms < 600_000 else None
    return ProbeResult(outcome, category, latency)


# ------------------------------------------------------------------------------------------------------------
# Service
# ------------------------------------------------------------------------------------------------------------

class IntegrationNotFound(LookupError):
    pass


class IntegrationTestUnsupported(RuntimeError):
    pass


def _iso(dt):
    return dt.isoformat() if dt else None


class IntegrationService:
    def __init__(self, session_factory: sessionmaker, store: SecretStore | None = None,
                 probes: dict[str, Callable[[SecretStore], ProbeResult]] | None = None) -> None:
        self._sf = session_factory
        self._store = store or get_secret_store()
        self._probes = probes

    def _state(self, s, code: str) -> IntegrationState | None:
        return s.scalar(select(IntegrationState).where(IntegrationState.integration_code == code))

    def describe(self, defn: IntegrationDef, state: IntegrationState | None) -> dict:
        creds = [{"slot": c.slot, "label": c.label, "external_name": c.external_name,
                  "configured": self._store.is_configured(c.external_name),
                  "source": self._store.source(c.external_name), "writable": bool(self._store.supports_write)}
                 for c in defn.credentials]
        configured = {c["slot"]: c["configured"] for c in creds}
        settings = {s.code: _setting(s) for s in defn.settings}
        enabled, classification = _runtime(defn, configured, settings)
        if state and state.last_test_at:
            health = {"status": "healthy" if state.last_test_outcome == "success" else "unhealthy",
                      "last_tested_at": _iso(state.last_test_at), "category": state.last_test_category,
                      "latency_ms": state.last_test_latency_ms}
        else:
            health = {"status": "not_tested", "last_tested_at": None, "category": None, "latency_ms": None}
        return {
            "code": defn.code, "name": defn.name, "category": defn.category,
            "category_label": CATEGORIES[defn.category], "adapter": defn.adapter, "description": defn.description,
            "classification": classification,
            "configuration_status": _configuration_status(configured, defn, settings),
            "slots": creds,
            "settings": [{"code": s.code, "label": s.label, "selected": settings[s.code]} for s in defn.settings],
            "runtime": {"enabled": enabled, "managed": "environment",
                        "toggle_supported": False,
                        "note": "Runtime state is owned by the deployment environment and changes need a deployment or restart."},
            "store": {"name": self._store.name, "writable": bool(self._store.supports_write)},
            "health": health,
            "test": {"supported": defn.test_supported, "note": defn.test_note},
            "validation_note": defn.validation_note,
        }

    def list(self) -> list[dict]:
        with self._sf() as s:
            states = {st.integration_code: st for st in s.scalars(select(IntegrationState)).all()}
        return [self.describe(d, states.get(d.code)) for d in REGISTRY.values()]

    def get(self, code: str) -> dict:
        defn = REGISTRY.get(code)
        if defn is None:
            raise IntegrationNotFound(code)
        with self._sf() as s:
            return self.describe(defn, self._state(s, code))

    def run_test(self, code: str, *, actor_user_id: int, audit: dict | None = None) -> dict:
        defn = REGISTRY.get(code)
        if defn is None:
            raise IntegrationNotFound(code)
        if not defn.test_supported or code not in (self._probes if self._probes is not None else PROBES):
            raise IntegrationTestUnsupported(code)
        result = run_probe(code, self._store, self._probes)
        with self._sf() as s:   # result row and audit event are ONE transaction
            st = self._state(s, code)
            if st is None:
                st = IntegrationState(integration_code=code)
                s.add(st)
            st.last_test_at, st.last_test_outcome = utcnow(), result.outcome
            st.last_test_category, st.last_test_latency_ms = result.category, result.latency_ms
            st.last_test_by_user_id = actor_user_id
            _stage(s, audit, integration=code, outcome=result.outcome, category=result.category)
            s.commit()
        return {"integration": code, "outcome": result.outcome, "category": result.category, "latency_ms": result.latency_ms}

    # Credential replacement: only when the active store supports writes. The value is validated structurally,
    # passed straight to the store and discarded; it is never returned, logged, audited or persisted here.
    @staticmethod
    def validate_credential_shape(value: object) -> str:
        if not isinstance(value, str) or not (8 <= len(value) <= 4096) or any(c.isspace() for c in value):
            raise ValueError("The credential must be 8 to 4096 characters with no whitespace.")
        return value

    def credential_slot(self, code: str, slot: str) -> CredentialSlot:
        defn = REGISTRY.get(code)
        if defn is None:
            raise IntegrationNotFound(code)
        match = next((c for c in defn.credentials if c.slot == slot), None)
        if match is None:
            raise IntegrationNotFound(f"{code}/{slot}")
        return match

    def write_credential(self, code: str, slot: str, value: str) -> None:
        cred = self.credential_slot(code, slot)
        if not self._store.supports_write:
            raise SecretStoreReadOnly("This credential is managed outside Ask4Mo and cannot be changed here.")
        self._store.set(cred.external_name, self.validate_credential_shape(value))

    def stats(self) -> dict:
        items = self.list()
        return {
            "total": len(items),
            "configured": sum(1 for i in items if i["configuration_status"] == "configured"),
            "runtime_active": sum(1 for i in items if i["classification"] == "runtime_active"),
            "not_tested": sum(1 for i in items if i["test"]["supported"] and i["health"]["status"] == "not_tested"),
            "unhealthy": sum(1 for i in items if i["health"]["status"] == "unhealthy"),
        }


def probe_environment_allowlist() -> list[str]:
    """Names only (for tests and the evaluator): every environment variable this module can read."""
    names = []
    for d in REGISTRY.values():
        names += [c.external_name for c in d.credentials] + [s.env_name for s in d.settings]
        if d.enabled_flag:
            names.append(d.enabled_flag)
    return sorted(set(names))

