"""Realtime voice — provider-neutral session minting (Capstone P7.5, C1).

This module is the SERVER seam for realtime voice. Its single job is to mint a **short-lived,
user-scoped session credential** for a realtime voice provider, so the browser can open a
low-latency WebRTC audio channel *directly to the provider* — Ask4Mo is never in the audio
path, stores no audio, and never sees a transcript here.

Hard boundaries (enforced + tested):
- **The long-lived provider key never leaves the server.** It is read as ``SecretStr`` via
  ``src.core.secrets.read_secret`` and used only to call the provider's session-creation
  endpoint. The value returned to the browser is only the provider's *ephemeral* client
  secret (short TTL) plus bounded, non-secret config.
- **The client never chooses the model, provider or voice.** Those are resolved
  server-authoritatively from a bounded allow-list (mirroring the P5 model policy —
  ``ModelOperation.REALTIME_VOICE``). A client-supplied slug is ignored.
- **Realtime is OFF by default.** With no key / flag off, ``build_realtime_provider`` returns
  ``None`` and the API reports the feature unavailable so the UI falls back to P7 turn-based.
- **Bounded cost.** Session duration, per-user concurrency and idle timeout are capped, and
  session creation is rate-limited (see ``RealtimeSessionLimiter``).

No provider call happens at import. ``FakeRealtimeProvider`` gives CI a deterministic path
with **zero** paid calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from src.core import secrets as _secrets
from src.llm.policy import ModelCapability, ModelOperation, resolve_policy

__all__ = [
    "RealtimeConfig",
    "RealtimeSessionRequest",
    "RealtimeSessionGrant",
    "RealtimeUnavailableError",
    "RealtimeProvider",
    "OpenAiRealtimeProvider",
    "FakeRealtimeProvider",
    "RealtimeSessionLimiter",
    "RateLimitExceeded",
    "SUPPORTED_REALTIME_LOCALES",
    "resolve_realtime_config",
    "build_realtime_provider",
    "realtime_policy_summary",
]

# The seven product locales (Capstone target). Realtime language selects a spoken-language
# hint ONLY; it never changes interface locale, dictation locale, or labour-market geography
# (§18). We keep the mapping deliberately small and explicit.
SUPPORTED_REALTIME_LOCALES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "pt", "nl")

# Bounds (env-overridable). Deliberately conservative — realtime audio is costly.
_DEFAULT_MAX_SESSION_SECONDS = 300      # a single live session is capped at 5 minutes
_DEFAULT_MAX_CONCURRENT_PER_USER = 1    # one live session per user at a time
_DEFAULT_IDLE_TIMEOUT_SECONDS = 60      # client must show activity within a minute
_DEFAULT_EPHEMERAL_TTL_SECONDS = 60     # time to *establish* the connection
_DEFAULT_SESSIONS_PER_WINDOW = 6        # session-creation rate limit …
_DEFAULT_RATE_WINDOW_SECONDS = 60       # … per user per rolling minute

# Env var names (documented in .env.example). The provider key mirrors OPENROUTER/GEMINI.
_ENV_ENABLED = "REALTIME_VOICE_ENABLED"
_ENV_PROVIDER = "REALTIME_VOICE_PROVIDER"
_ENV_KEY = "REALTIME_VOICE_API_KEY"
_ENV_MODEL = "REALTIME_VOICE_MODEL"
_ENV_VOICE = "REALTIME_VOICE_VOICE"
_ENV_BASE_URL = "REALTIME_VOICE_BASE_URL"
_ENV_MAX_SESSION = "REALTIME_VOICE_MAX_SESSION_SECONDS"
_ENV_MAX_CONCURRENT = "REALTIME_VOICE_MAX_CONCURRENT_PER_USER"

_DEFAULT_PROVIDER = "openai_realtime"
_DEFAULT_MODEL = "gpt-realtime"           # server default; override via env, never by client
_DEFAULT_VOICE = "alloy"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class RealtimeUnavailableError(RuntimeError):
    """Realtime voice is not configured/available — the caller must fall back to P7."""


class RateLimitExceeded(RuntimeError):
    """Too many realtime session creations for this user in the current window."""


@dataclass(frozen=True)
class RealtimeConfig:
    """Server-authoritative realtime configuration. Holds NO secret value (only whether one
    is present); the key itself is read separately and never stored on this object."""

    enabled: bool
    provider: str
    configured: bool                 # a long-lived key is present (booleans only)
    model: str
    voice: str
    base_url: str
    max_session_seconds: int
    max_concurrent_per_user: int
    idle_timeout_seconds: int
    ephemeral_ttl_seconds: int
    sessions_per_window: int
    rate_window_seconds: int

    @property
    def available(self) -> bool:
        """Realtime can actually run: enabled AND a key is configured."""
        return self.enabled and self.configured

    def safe_dict(self) -> dict:
        """Non-secret projection for /admin (booleans/labels only — no key, no URL secrets)."""
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "available": self.available,
            "provider": self.provider,
            "model": self.model,
            "voice": self.voice,
            "max_session_seconds": self.max_session_seconds,
            "max_concurrent_per_user": self.max_concurrent_per_user,
        }


@dataclass(frozen=True)
class RealtimeSessionRequest:
    """A validated request to open a realtime session. All fields are bounded/allow-listed;
    the client may express a *language preference* and a *surface*, nothing about the model."""

    user_id: int
    locale: str = "en"               # one of SUPPORTED_REALTIME_LOCALES (else coerced to en)
    surface: str = "practice"        # "practice" | "prepare"
    interview_session_id: str | None = None

    def normalized_locale(self) -> str:
        base = (self.locale or "en").split("-")[0].strip().lower()
        return base if base in SUPPORTED_REALTIME_LOCALES else "en"


@dataclass(frozen=True)
class RealtimeSessionGrant:
    """What the browser receives — the EPHEMERAL secret plus bounded, non-secret config.

    ``client_secret`` is the provider's short-lived token, NOT the server key. Nothing here
    is ever logged; observability sees only counts/booleans/duration buckets.
    """

    provider: str
    model: str
    voice: str
    locale: str
    client_secret: str               # ephemeral, short-lived — safe to hand to the browser
    expires_at: float                # epoch seconds
    session_id: str                  # opaque, user-scoped
    base_url: str
    max_session_seconds: int
    idle_timeout_seconds: int

    def public_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "voice": self.voice,
            "locale": self.locale,
            "client_secret": self.client_secret,
            "expires_at": self.expires_at,
            "session_id": self.session_id,
            "base_url": self.base_url,
            "max_session_seconds": self.max_session_seconds,
            "idle_timeout_seconds": self.idle_timeout_seconds,
        }


class RealtimeProvider(Protocol):
    """Provider-neutral realtime session minter. Implementations must never return the
    long-lived key and must scope the session to ``request.user_id``."""

    name: str

    def mint_session(self, request: RealtimeSessionRequest) -> RealtimeSessionGrant:
        ...


def _uses_realtime_policy() -> bool:
    """Cross-check the model-policy boundary: REALTIME_VOICE must resolve to the REALTIME
    capability with no chat slug (so a client slug can never be attributed to it)."""
    policy = resolve_policy(ModelOperation.REALTIME_VOICE, None)
    return policy.capability is ModelCapability.REALTIME and policy.model_id is None


def realtime_policy_summary() -> dict:
    """Safe projection of the realtime model policy (for observability/docs)."""
    return resolve_policy(ModelOperation.REALTIME_VOICE, None).to_dict()


class OpenAiRealtimeProvider:
    """Mints an ephemeral realtime session against an OpenAI-Realtime-shaped endpoint.

    The long-lived key is passed in as ``SecretStr`` and used ONLY as the Bearer credential
    to the provider's session-creation endpoint; it is never returned or logged. The browser
    receives only the ephemeral ``client_secret`` from the provider response.

    NOTE (honest status): this path is architecture-complete but **LIVE-UNVALIDATED** — no
    authorised realtime key exists in this project, so it has never made a real call. The
    request/response shape follows the documented OpenAI Realtime sessions API; the exact
    endpoint is env-overridable to tolerate provider API evolution.
    """

    name = "openai_realtime"

    def __init__(self, *, config: RealtimeConfig, api_key, http_post=None) -> None:
        self._config = config
        self._api_key = api_key  # SecretStr — never unwrapped except into the Bearer header
        # http_post is injectable purely for tests; default builds a bounded httpx call.
        self._http_post = http_post

    def mint_session(self, request: RealtimeSessionRequest) -> RealtimeSessionGrant:
        if not _uses_realtime_policy():  # defence in depth
            raise RealtimeUnavailableError("realtime policy boundary not satisfied")
        locale = request.normalized_locale()
        payload = {
            # Server chooses model/voice — NOT the client.
            "model": self._config.model,
            "voice": self._config.voice,
        }
        url = f"{self._config.base_url.rstrip('/')}/realtime/sessions"
        data = self._post(url, payload)
        secret, expires_at = _parse_client_secret(data, self._config.ephemeral_ttl_seconds)
        session_id = str(data.get("id") or f"rt_{int(time.time()*1000):x}")
        return RealtimeSessionGrant(
            provider=self.name,
            model=self._config.model,
            voice=self._config.voice,
            locale=locale,
            client_secret=secret,
            expires_at=expires_at,
            session_id=session_id,
            base_url=self._config.base_url,
            max_session_seconds=self._config.max_session_seconds,
            idle_timeout_seconds=self._config.idle_timeout_seconds,
        )

    def _post(self, url: str, payload: dict) -> dict:
        if self._http_post is not None:
            return self._http_post(url, payload, self._bearer())
        import httpx  # local import: no network dependency at module import

        headers = {"Authorization": self._bearer(), "Content-Type": "application/json"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _bearer(self) -> str:
        # The ONLY place the long-lived key is unwrapped, straight into the header string.
        return f"Bearer {self._api_key.get_secret_value()}"


def _parse_client_secret(data: dict, default_ttl: int) -> tuple[str, float]:
    """Extract the ephemeral client secret + expiry from a provider response, tolerantly."""
    cs = data.get("client_secret")
    if isinstance(cs, dict):
        value = cs.get("value")
        expires_at = cs.get("expires_at")
    else:
        value = cs if isinstance(cs, str) else data.get("value")
        expires_at = data.get("expires_at")
    if not value or not isinstance(value, str):
        raise RealtimeUnavailableError("provider did not return an ephemeral client secret")
    try:
        exp = float(expires_at) if expires_at is not None else time.time() + default_ttl
    except (TypeError, ValueError):
        exp = time.time() + default_ttl
    return value, exp


class FakeRealtimeProvider:
    """Deterministic provider for tests/CI — mints a fake ephemeral secret, zero paid calls.

    It asserts the boundary directly: it is *constructed without any long-lived key* and can
    only ever emit an obviously-ephemeral token, so a test can prove no server key is leaked.
    """

    name = "fake_realtime"

    def __init__(self, *, config: RealtimeConfig | None = None) -> None:
        self._config = config or resolve_realtime_config()
        self._counter = 0

    def mint_session(self, request: RealtimeSessionRequest) -> RealtimeSessionGrant:
        self._counter += 1
        locale = request.normalized_locale()
        now = time.time()
        return RealtimeSessionGrant(
            provider=self.name,
            model=self._config.model,
            voice=self._config.voice,
            locale=locale,
            client_secret=f"ephemeral-fake-{request.user_id}-{self._counter}",
            expires_at=now + self._config.ephemeral_ttl_seconds,
            session_id=f"rt_fake_{request.user_id}_{self._counter}",
            base_url=self._config.base_url,
            max_session_seconds=self._config.max_session_seconds,
            idle_timeout_seconds=self._config.idle_timeout_seconds,
        )


class RealtimeSessionLimiter:
    """Bounded, in-memory, per-user session-creation rate limit + concurrency counter.

    LOCAL-ONLY (single process): a production deployment behind multiple workers needs a
    shared store (Redis) — documented as a production dependency (§26). Even local, it stops
    a browser from creating unbounded provider sessions.
    """

    def __init__(
        self,
        *,
        sessions_per_window: int = _DEFAULT_SESSIONS_PER_WINDOW,
        window_seconds: int = _DEFAULT_RATE_WINDOW_SECONDS,
        max_concurrent_per_user: int = _DEFAULT_MAX_CONCURRENT_PER_USER,
        clock=time.monotonic,
    ) -> None:
        self._per_window = sessions_per_window
        self._window = window_seconds
        self._max_concurrent = max_concurrent_per_user
        self._clock = clock
        self._events: dict[int, list[float]] = {}
        self._active: dict[int, int] = {}

    def check_and_reserve(self, user_id: int) -> None:
        """Raise ``RateLimitExceeded`` if the user is over the window rate or concurrency."""
        now = self._clock()
        recent = [t for t in self._events.get(user_id, []) if now - t < self._window]
        if len(recent) >= self._per_window:
            self._events[user_id] = recent
            raise RateLimitExceeded("too many realtime sessions; try again shortly")
        if self._active.get(user_id, 0) >= self._max_concurrent:
            raise RateLimitExceeded("a realtime session is already active for this user")
        recent.append(now)
        self._events[user_id] = recent
        self._active[user_id] = self._active.get(user_id, 0) + 1

    def release(self, user_id: int) -> None:
        """Mark a user's active session as ended (idempotent, never negative)."""
        self._active[user_id] = max(0, self._active.get(user_id, 0) - 1)


def _read_int(name: str, default: int) -> int:
    raw = _secrets.read_setting(name)
    if raw is None:
        return default
    try:
        val = int(raw)
        return val if val > 0 else default
    except ValueError:
        return default


def resolve_realtime_config() -> RealtimeConfig:
    """Build the realtime config from env/secrets. Reads whether a key is present (boolean);
    never stores the key value on the returned object."""
    key = _secrets.read_secret(_ENV_KEY)
    return RealtimeConfig(
        enabled=_secrets.read_bool(_ENV_ENABLED, default=False),
        provider=(_secrets.read_setting(_ENV_PROVIDER) or _DEFAULT_PROVIDER),
        configured=key is not None,
        model=(_secrets.read_setting(_ENV_MODEL) or _DEFAULT_MODEL),
        voice=(_secrets.read_setting(_ENV_VOICE) or _DEFAULT_VOICE),
        base_url=(_secrets.read_setting(_ENV_BASE_URL) or _DEFAULT_BASE_URL),
        max_session_seconds=_read_int(_ENV_MAX_SESSION, _DEFAULT_MAX_SESSION_SECONDS),
        max_concurrent_per_user=_read_int(_ENV_MAX_CONCURRENT, _DEFAULT_MAX_CONCURRENT_PER_USER),
        idle_timeout_seconds=_DEFAULT_IDLE_TIMEOUT_SECONDS,
        ephemeral_ttl_seconds=_DEFAULT_EPHEMERAL_TTL_SECONDS,
        sessions_per_window=_DEFAULT_SESSIONS_PER_WINDOW,
        rate_window_seconds=_DEFAULT_RATE_WINDOW_SECONDS,
    )


def build_realtime_provider(config: RealtimeConfig | None = None) -> RealtimeProvider | None:
    """Return a live provider when realtime is enabled AND a key is configured, else ``None``
    (the caller then reports unavailable and the UI falls back to P7 turn-based voice)."""
    cfg = config or resolve_realtime_config()
    if not cfg.available:
        return None
    key = _secrets.read_secret(_ENV_KEY)
    if key is None:  # defensive: available implied configured, but never build without a key
        return None
    # Only the OpenAI-Realtime shape is implemented; other providers are a future adapter.
    return OpenAiRealtimeProvider(config=cfg, api_key=key)
