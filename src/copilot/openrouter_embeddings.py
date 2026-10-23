"""OpenRouter embedding provider (02B completion, REVIEW-04, OD-EMBED provisional).

``POST {OPENROUTER_BASE_URL}/embeddings`` with the OpenAI-compatible body documented by OpenRouter (``model``, ``input`` = array of non-empty strings,
``encoding_format`` = ``float``, optional ``dimensions``); the response is ``{data: [{embedding, index}], usage: {prompt_tokens, total_tokens, cost?}}``.

SPEND CONTROL IS NOT HERE. The request goes through a plain ``httpx.Client``; the 05C governor wraps ``httpx.Client.send`` once for the whole
process, so reservation, per-request limits, the approved-budget marker, the ``embedding`` category ceiling, the kill switch, duplicate/unknown-outcome
refusal and token/cost/latency accounting apply automatically. This module adds NO second spend control and has NO path around the chokepoint. It only
REFUSES to send when no open governor is installed (so a process that forgot to enforce the budget can never make an ungoverned paid call).

What this module guarantees at its own boundary:

* the model id, dimensions and version are configuration (see ``resolve_embedding_plan``); the key is ``CopilotConfig.api_key`` (read through the
  secrets seam), used only as a Bearer header, never stored in a repr, error, log or cache;
* identical texts are sent once per call and cached (bounded) per embedder, so a build never pays twice for the same chunk;
* batches are bounded by input count and by the pessimistic token estimate the governor itself uses (and by the governor's per-request input limit
  when one is installed); an input above the model's context is refused, never truncated;
* retries: at most ``OPENROUTER_EMBED_MAX_RETRIES`` and ONLY for connect-phase transport errors (the request provably never reached OpenRouter). A
  read timeout, a 5xx or a lost connection is an UNKNOWN outcome and is never re-sent here (the governor also refuses an identical re-send);
* the response is validated before use: object shape, vector count equals input count, ``index`` values (when present) a permutation of the inputs,
  every vector a list of finite real numbers of exactly the declared dimensions. Anything else raises :class:`EmbeddingProviderError`
  (``unexpected_response`` / ``dimension_mismatch``); partial, padded or zero vectors are never returned and a failed batch fails the whole call;
* every failure is an :class:`EmbeddingProviderError` with a FIXED code (provider text is never carried); a governor refusal is
  ``budget_refused`` with the governor's own stable ``reason``. Nothing ever falls back to another embedder.
"""

from __future__ import annotations

import json
import math
import time
from collections import OrderedDict
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.copilot.embedding_catalogue import ModelFacts, facts_for
from src.copilot.embeddings import BaseEmbedder, EmbeddingConfigurationError, EmbeddingProviderError
from src.llm.budget import governor as _governor
from src.llm.budget.errors import BudgetError

__all__ = ["OpenRouterEmbedder", "OPENROUTER_HOST", "plan_dimensions"]

OPENROUTER_HOST = "openrouter.ai"


def _estimate(texts: list[str]) -> int:
    """The governor's own pessimistic estimator applied to the exact ``input`` JSON we send (so our batch check implies the governor's)."""
    return _governor.estimate_tokens(json.dumps(texts, ensure_ascii=False, default=str))


def plan_dimensions(model: str, configured: int | None) -> tuple[int | None, bool, str | None]:
    """``(declared dimensions, send the dimensions parameter, problem code)`` for ``model`` and an optional configured size. Pure.

    * known model, nothing configured: its native size, parameter not sent;
    * known model that supports ``dimensions``: a smaller configured size is sent as the parameter; a larger one is refused;
    * known model that does not support it: a configured size other than native is refused;
    * unknown model: the configured size is the declared one (required), parameter never sent (the response length is the proof)."""
    facts: ModelFacts | None = facts_for(model)
    if facts is None:
        return (configured, False, None if configured else "embedding_dimensions_unknown")
    if not configured or configured == facts.native_dimensions:
        return facts.native_dimensions, False, None
    if not facts.supports_dimensions:
        return configured, False, "embedding_dimensions_unsupported"
    if configured > facts.native_dimensions:
        return configured, False, "embedding_dimensions_exceed_native"
    return configured, True, None


def base_url_problem(base_url: str | None) -> bool:
    """True when the OpenRouter base URL is not https on the governed OpenRouter host (a different host would bypass the governor's classification)."""
    try:
        u = urlparse(base_url or "")
        return not (u.scheme == "https" and (u.hostname or "").lower() == OPENROUTER_HOST and not u.username and not u.password)
    except Exception:  # noqa: BLE001
        return True


class OpenRouterEmbedder(BaseEmbedder):
    """Embeddings through OpenRouter's ``/embeddings`` endpoint. ``client`` and ``sleep`` are injectable for tests (a ``MockTransport`` client)."""

    provider = "openrouter"

    def __init__(self, config: CopilotConfig, *, client: httpx.Client | None = None, require_governor: bool = True,
                 sleep: Callable[[float], None] = time.sleep, max_retries: int = constants.OPENROUTER_EMBED_MAX_RETRIES) -> None:
        key = config.api_key
        if key is None or not key.get_secret_value().strip():
            raise EmbeddingConfigurationError(["semantic_credentials_missing"], fields=("credentials",)) from None
        model = (config.embedding_model or "").strip()
        if "/" not in model:
            raise EmbeddingConfigurationError(["embedding_model_not_configured"], fields=("model",))
        if base_url_problem(config.base_url):
            raise EmbeddingConfigurationError(["embedding_base_url_invalid"], fields=("base_url",))
        dims, send_dims, problem = plan_dimensions(model, config.embedding_dimensions)
        if problem or dims is None:
            raise EmbeddingConfigurationError([problem or "embedding_dimensions_unknown"], fields=("dimensions",))
        self.model = model
        self.dimensions = int(dims)
        self.version = config.embedding_version or constants.OPENROUTER_EMBEDDING_VERSION
        self._send_dimensions = send_dims
        self._facts = facts_for(model)
        self._url = config.base_url.rstrip("/") + "/embeddings"
        self._headers = {"Authorization": f"Bearer {key.get_secret_value().strip()}", "Content-Type": "application/json",
                         "HTTP-Referer": config.app_referer, "X-Title": config.app_title}
        self._client = client
        self._timeout = httpx.Timeout(config.read_timeout_seconds, connect=config.connect_timeout_seconds)
        self._require_governor = require_governor
        self._sleep = sleep
        self._max_retries = max(0, min(int(max_retries), 2))
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self.requests_sent = 0            # provider requests attempted by this embedder (retries included)
        self.cache_hits = 0
        self.prompt_tokens = 0            # sum of provider-REPORTED prompt tokens (responses without usage add nothing: unknown is never 0)
        self.responses_without_usage = 0

    def __repr__(self) -> str:                                    # never includes the key
        return f"OpenRouterEmbedder(model={self.model!r}, dimensions={self.dimensions}, version={self.version!r})"

    # ------------------------------------------------------------------ bounds
    def _batch_token_bound(self) -> int:
        bound = constants.OPENROUTER_EMBED_MAX_BATCH_TOKENS
        gov = _governor.active_governor()
        if gov is not None and gov.config is not None:
            bound = min(bound, gov.config.limits.max_input_tokens)
        return bound

    def _check_governor(self) -> None:
        if not self._require_governor:
            return
        gov = _governor.active_governor()
        if gov is None:
            raise EmbeddingProviderError("budget_governor_not_installed")
        if not gov.is_open:
            err = EmbeddingProviderError("budget_refused")
            err.reason = gov.closed_reason or "governor_closed"
            raise err

    def _batches(self, texts: list[str]) -> list[list[str]]:
        bound = self._batch_token_bound()
        context = self._facts.context_tokens if self._facts else None
        out: list[list[str]] = []
        cur: list[str] = []
        for t in texts:
            single = _estimate([t])
            if (context is not None and single > context) or single > bound:
                raise EmbeddingProviderError("input_too_large")
            if cur and (len(cur) >= constants.OPENROUTER_EMBED_MAX_BATCH_INPUTS or _estimate(cur + [t]) > bound):
                out.append(cur)
                cur = []
            cur.append(t)
        if cur:
            out.append(cur)
        return out

    # ------------------------------------------------------------------ request
    def _body(self, batch: list[str]) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "input": batch, "encoding_format": "float"}
        if self._send_dimensions:
            body["dimensions"] = self.dimensions
        return body

    def _post(self, batch: list[str]) -> httpx.Response:
        own = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout)        # follow_redirects stays False: the key is never re-sent elsewhere
        try:
            attempt = 0
            while True:
                self.requests_sent += 1
                try:
                    return client.post(self._url, json=self._body(batch), headers=self._headers, timeout=self._timeout)
                except BudgetError as exc:
                    err = EmbeddingProviderError("budget_refused")
                    err.reason = exc.reason
                    raise err from None
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    if attempt >= self._max_retries:
                        raise EmbeddingProviderError("network") from None
                    attempt += 1
                    self._sleep(min(2.0 * attempt, 5.0))
                except httpx.TimeoutException:
                    raise EmbeddingProviderError("timeout") from None       # unknown outcome: never re-sent
                except httpx.HTTPError:
                    raise EmbeddingProviderError("network") from None
        finally:
            if own:
                client.close()

    @staticmethod
    def _status_error(status: int) -> EmbeddingProviderError:
        code = {401: "provider_auth", 403: "provider_auth", 402: "provider_credits", 413: "payload_too_large", 429: "rate_limited"}.get(status)
        if code is None:
            code = "provider_unavailable" if status >= 500 else "provider_rejected"
        return EmbeddingProviderError(code)

    def _validated(self, response: httpx.Response, expected: int) -> list[list[float]]:
        if response.status_code != 200:
            raise self._status_error(response.status_code)
        try:
            payload = response.json()
        except ValueError:
            raise EmbeddingProviderError("unexpected_response") from None
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != expected or "error" in payload:
            raise EmbeddingProviderError("unexpected_response")
        usage = payload.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise EmbeddingProviderError("unexpected_response")
        rows: list[tuple[int, list[float]]] = []
        for pos, item in enumerate(data):
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise EmbeddingProviderError("unexpected_response")
            idx = item.get("index", pos)
            if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < expected:
                raise EmbeddingProviderError("unexpected_response")
            vec = item["embedding"]
            if len(vec) != self.dimensions:
                raise EmbeddingProviderError("dimension_mismatch")
            clean: list[float] = []
            for x in vec:
                if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                    raise EmbeddingProviderError("unexpected_response")
                clean.append(float(x))
            rows.append((idx, clean))
        if sorted(i for i, _ in rows) != list(range(expected)):                  # duplicated or missing index: a permutation or nothing
            raise EmbeddingProviderError("unexpected_response")
        if isinstance(usage, dict) and isinstance(usage.get("prompt_tokens"), int) and not isinstance(usage.get("prompt_tokens"), bool):
            self.prompt_tokens += usage["prompt_tokens"]
        else:
            self.responses_without_usage += 1
        return [v for _, v in sorted(rows, key=lambda r: r[0])]

    # ------------------------------------------------------------------ cache
    def _remember(self, text: str, vec: list[float]) -> None:
        self._cache[text] = vec
        self._cache.move_to_end(text)
        while len(self._cache) > constants.OPENROUTER_EMBED_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    # ------------------------------------------------------------------ interface
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        texts = list(texts)
        if any(not isinstance(t, str) or not t.strip() for t in texts):
            raise EmbeddingProviderError("empty_input")                          # the endpoint rejects empty strings; never invent a vector
        if not texts:
            return []
        unique = list(dict.fromkeys(texts))
        known = {t: self._cache[t] for t in unique if t in self._cache}          # captured now: later eviction can never lose a vector of THIS call
        missing = [t for t in unique if t not in known]
        self.cache_hits += len(known)
        if missing:
            batches = self._batches(missing)                                     # all bounds checked BEFORE the first request
            self._check_governor()
            for batch in batches:
                vectors = self._validated(self._post(batch), len(batch))
                known.update(zip(batch, vectors))                                # a failed later batch raises: nothing partial is returned or cached
            for t in missing:
                self._remember(t, known[t])
        return [list(known[t]) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
