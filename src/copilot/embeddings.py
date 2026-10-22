"""Embedding abstraction for Career Intelligence Copilot.

The rest of the system depends on the small :class:`BaseEmbedder` interface, not
on any one provider, so the embedding backend can change without touching
retrieval, the vector store or the RAG chain.

Two providers ship:

* :class:`OpenAIEmbedder` — OpenAI-compatible embeddings API (real semantic
  quality). Needs an embedding API key; the base URL is configurable because
  OpenRouter does not serve embeddings for every model.
* :class:`LocalHashEmbedder` — a dependency-free, deterministic embedder used as
  an offline fallback and in tests. It hashes tokens into a fixed-width vector
  (a lexical signal, not true semantics), so the app always runs even with no
  key and no network. Its limits are documented in ``docs/rag.md``.

:func:`build_embedder` picks a provider from configuration.

02B (REVIEW-04 R1/R4/R5): the choice is EXPLICIT and recorded. :func:`resolve_embedding_plan` turns the configuration into a typed
:class:`EmbeddingResolution` (provider, model, recorded version, dimensions, quality mode, problems). In a HOSTED environment (staging,
production, or an unrecognised ``API_ENV``) the lexical hash embedder is never an acceptable runtime: a configuration that would resolve to it
(explicitly or because no semantic credential exists), an unknown provider, or a semantic model whose dimensions are unknown makes
:func:`build_embedder` raise the typed, secret-free :class:`EmbeddingConfigurationError` instead of silently degrading. Development stays
permissive and is visibly labelled ``OFFLINE LEXICAL (development only)``. A provider error at call time raises
:class:`EmbeddingProviderError`; nothing ever falls back to the hash embedder at call time.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.copilot import constants
from src.copilot.config import CopilotConfig
from src.core.errors import ConfigError
from src.knowledge_admin.contracts import EmbedderIdentity

__all__ = [
    "EmbeddingConfigurationError",
    "EmbeddingProviderError",
    "EmbeddingResolution",
    "resolve_embedding_plan",
    "current_environment",
    "BaseEmbedder",
    "OpenAIEmbedder",
    "LocalHashEmbedder",
    "build_embedder",
    "embedding_status",
]


# --- 02B: typed errors, environment and explicit resolution -------------------


class EmbeddingConfigurationError(ConfigError, ValueError):
    """The embedding configuration is not acceptable for this environment (hosted + hash/lexical, missing credentials, unknown provider or
    dimensions). ``codes`` are fixed, secret-free codes; ``fields`` name the configuration fields involved (never their values). Also a
    ``ValueError`` so existing callers that handled a missing key keep working."""

    def __init__(self, codes: list[str], *, environment: str = "unknown", fields: tuple[str, ...] = ()) -> None:
        super().__init__("embedding configuration refused: " + ", ".join(codes))
        self.codes = list(codes)
        self.environment = environment
        self.fields = tuple(fields)


class EmbeddingProviderError(Exception):
    """A semantic provider call failed or returned unusable vectors. The provider's own message is NEVER carried (it can contain request
    details); callers see only a fixed code. There is no fallback to another embedder."""

    #: For ``budget_refused``: the governor's own stable, secret-free reason code (else ``None``).
    reason: str | None = None

    def __init__(self, code: str = "provider_error") -> None:
        super().__init__(f"embedding provider error: {code}")
        self.code = code


def current_environment(environment: str | None = None) -> str:
    """``development`` | ``staging`` | ``production`` | ``unknown`` from ``API_ENV`` (or the argument). Same normaliser as the knowledge guard."""
    from src.knowledge_admin.config import normalise_environment

    return normalise_environment(environment if environment is not None else os.environ.get("API_ENV", "development"))


@dataclass(frozen=True)
class EmbeddingResolution:
    """What the configuration resolves to, with no client built and no network. ``problems`` are the codes that make it unacceptable in THIS
    environment (always empty means usable); ``warnings`` are development-only labels."""

    environment: str
    hosted: bool
    configured_provider: str
    provider: str
    model: str
    version: str
    dimensions: int | None
    problems: tuple[str, ...] = ()
    problem_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def semantic(self) -> bool:
        return self.provider != "local"

    @property
    def approved(self) -> bool:
        return not self.problems

    @property
    def quality_mode(self) -> str:
        return "SEMANTIC" if self.semantic else "OFFLINE LEXICAL"

    @property
    def label(self) -> str:
        if self.semantic:
            return "semantic embedder"
        return "OFFLINE LEXICAL (development only, NOT production quality)" if not self.hosted else "OFFLINE LEXICAL (refused in a hosted environment)"

    def identity(self) -> EmbedderIdentity:
        return EmbedderIdentity(self.provider, self.model, self.version, self.dimensions)

    def to_safe_dict(self) -> dict:
        return {"environment": self.environment, "hosted": self.hosted, "configured_provider": self.configured_provider,
                "provider": self.provider, "model": self.model, "version": self.version, "dimensions": self.dimensions,
                "quality_mode": self.quality_mode, "label": self.label, "approved": self.approved, "problems": list(self.problems),
                "problem_fields": list(self.problem_fields), "warnings": list(self.warnings)}


def _has_key(secret: Any) -> bool:
    try:
        return bool(secret is not None and secret.get_secret_value().strip())
    except Exception:  # noqa: BLE001
        return False


def resolve_embedding_plan(config: CopilotConfig, *, environment: str | None = None) -> EmbeddingResolution:
    """Pure, offline resolution of the embedding configuration for ``environment`` (default: ``API_ENV``). Never builds a client, never reads a
    key's value, never raises. Hosted environments report every condition that would degrade quality as a problem; development reports only the
    conditions that were already hard errors (an explicit semantic provider without a key) and labels the rest as warnings."""
    env = current_environment(environment)
    hosted = env != "development"
    configured = (getattr(config, "embedding_provider", None) or "auto").lower()
    known = configured in ("auto", "openai", "local", "openrouter")
    dedicated = _has_key(getattr(config, "embedding_api_key", None))
    any_key = _has_key(getattr(config, "embedding_key", None))
    if configured == "local":
        semantic = False
    elif configured in ("openai", "openrouter"):
        semantic = True
    else:                                    # auto (or an unrecognised value, treated as auto in development): semantic only with a DEDICATED key
        semantic = dedicated
    problems: list[str] = []
    fields: list[str] = []
    warnings: list[str] = []

    def problem(code: str, field: str) -> None:
        if code not in problems:
            problems.append(code)
        if field not in fields:
            fields.append(field)

    if not known and hosted:
        problem("embedding_provider_unknown", "provider")
    if semantic and configured == "openrouter":
        # 02B OpenRouter adapter: the model id comes from configuration ONLY (an OpenRouter id is "vendor/model"; the OpenAI-style default is not one),
        # the key is the OpenRouter key, the host must be the governed OpenRouter host and the dimensions must be provable. Hard errors in EVERY environment.
        from src.copilot.openrouter_embeddings import base_url_problem, plan_dimensions

        provider, model = "openrouter", str(getattr(config, "embedding_model", None) or "")
        version = getattr(config, "embedding_version", None) or constants.OPENROUTER_EMBEDDING_VERSION
        if "/" not in model:
            problem("embedding_model_not_configured", "model")
        if not _has_key(getattr(config, "api_key", None)):
            problem("semantic_credentials_missing", "credentials")
        if base_url_problem(getattr(config, "base_url", None)):
            problem("embedding_base_url_invalid", "base_url")
        dims, _send, dim_problem = plan_dimensions(model, getattr(config, "embedding_dimensions", None))
        if dim_problem:
            problem(dim_problem, "dimensions")
    elif semantic:
        provider, model = "openai", getattr(config, "embedding_model", None) or constants.DEFAULT_EMBEDDING_MODEL
        version = getattr(config, "embedding_version", None) or constants.OPENAI_EMBEDDING_VERSION
        dims = getattr(config, "embedding_dimensions", None) or constants.KNOWN_EMBEDDING_DIMENSIONS.get(str(model))
        if configured == "openai" and not any_key:
            problem("semantic_credentials_missing", "credentials")       # a hard error in every environment (as before 02B)
        if dims is None:
            if hosted:
                problem("embedding_dimensions_unknown", "dimensions")
            else:
                dims = constants.OPENAI_EMBEDDING_DIMENSIONS
                warnings.append("embedding_dimensions_assumed")
    else:
        provider, model, version, dims = "local", constants.LOCAL_EMBEDDING_MODEL, constants.LOCAL_EMBEDDING_VERSION, constants.LOCAL_EMBEDDING_DIMENSIONS
        if hosted:
            problem("hash_embedder_not_allowed", "provider")
            if configured != "local":
                problem("semantic_credentials_missing", "credentials")   # the reason the semantic embedder was not selected
        else:
            warnings.append("lexical_hash_embedder_development_only")
            if configured != "local":
                warnings.append("semantic_credentials_missing_fallback_to_lexical")
    return EmbeddingResolution(env, hosted, configured, provider, str(model), str(version), dims, tuple(problems), tuple(fields), tuple(warnings))


class BaseEmbedder(ABC):
    """Minimal embedding interface the rest of the app depends on."""

    #: Provider label, e.g. "openai" or "local".
    provider: str
    #: Model identifier for provenance/logging.
    model: str
    #: Vector dimensionality.
    dimensions: int
    #: Recorded embedding-configuration version (02B); ``None`` for an embedder that does not declare one (treated as unknown by manifests).
    version: str | None = None

    def identity(self) -> EmbedderIdentity:
        """Non-secret identity recorded in index manifests and compared at query time."""
        return EmbedderIdentity(getattr(self, "provider", None), getattr(self, "model", None), self.version,
                                getattr(self, "dimensions", None))

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents (index time)."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query (retrieval time)."""

    def describe(self) -> dict[str, Any]:
        """Non-secret description for the UI / manifests."""
        return {
            "provider": self.provider,
            "model": self.model,
            "dimensions": self.dimensions,
            "version": self.version,
        }


# --- Local, dependency-free fallback -----------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class LocalHashEmbedder(BaseEmbedder):
    """Deterministic hashing embedder — no dependencies, no network.

    Each token is hashed into a bucket and weighted by a sublinear term count;
    the resulting vector is L2-normalised so cosine similarity is meaningful.
    This captures lexical overlap only, but makes the whole RAG pipeline runnable
    and fully testable offline. Real semantic retrieval uses :class:`OpenAIEmbedder`.
    """

    provider = "local"
    version = constants.LOCAL_EMBEDDING_VERSION

    def __init__(self, dimensions: int = constants.LOCAL_EMBEDDING_DIMENSIONS) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions
        self.model = constants.LOCAL_EMBEDDING_MODEL

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        counts: dict[str, int] = {}
        for token in _TOKEN_RE.findall(text.lower()):
            counts[token] = counts.get(token, 0) + 1
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            # Sign bit spreads tokens across the space so overlaps don't all add.
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector  # empty/whitespace text -> zero vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


# --- OpenAI-compatible provider ----------------------------------------------


class OpenAIEmbedder(BaseEmbedder):
    """Embeddings via an OpenAI-compatible API (real semantic quality).

    Wraps ``langchain_openai.OpenAIEmbeddings`` (lazily imported). The key is
    read from ``SecretStr`` only at construction and handed straight to the
    client — never logged. ``embeddings_cls`` can be injected in tests.

    02B: dimensions and version come from the explicit configuration (known-model table or ``COPILOT_EMBEDDING_DIMENSIONS``; recorded
    ``version``); a call failure raises :class:`EmbeddingProviderError` with a fixed code (the provider message can echo request details) and
    every returned vector is checked against the declared dimensions. There is no fallback to another embedder.
    """

    provider = "openai"

    def __init__(
        self,
        config: CopilotConfig,
        *,
        embeddings_cls: Any | None = None,
    ) -> None:
        key = config.embedding_key
        if key is None or not key.get_secret_value().strip():
            raise EmbeddingConfigurationError(
                ["semantic_credentials_missing"], fields=("credentials",),
            ) from None
        self.model = config.embedding_model
        self.dimensions = (config.embedding_dimensions or constants.KNOWN_EMBEDDING_DIMENSIONS.get(self.model)
                           or constants.OPENAI_EMBEDDING_DIMENSIONS)
        self.version = config.embedding_version or constants.OPENAI_EMBEDDING_VERSION

        if embeddings_cls is None:
            try:
                from langchain_openai import OpenAIEmbeddings as embeddings_cls  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dep
                raise EmbeddingConfigurationError(["semantic_provider_unavailable"], fields=("provider",)) from exc

        self._client = embeddings_cls(
            model=self.model,
            api_key=key.get_secret_value(),
            base_url=config.embedding_base_url,
        )

    def _checked(self, vectors: list[list[float]], expected: int) -> list[list[float]]:
        if not isinstance(vectors, list) or len(vectors) != expected:
            raise EmbeddingProviderError("unexpected_response")
        for v in vectors:
            if not hasattr(v, "__len__") or len(v) != self.dimensions:
                raise EmbeddingProviderError("dimension_mismatch")
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        texts = list(texts)
        try:
            vectors = self._client.embed_documents(texts)
        except Exception:  # noqa: BLE001 - provider text is never propagated
            raise EmbeddingProviderError("provider_error") from None
        return self._checked(vectors, len(texts))

    def embed_query(self, text: str) -> list[float]:
        try:
            vector = self._client.embed_query(text)
        except Exception:  # noqa: BLE001
            raise EmbeddingProviderError("provider_error") from None
        return self._checked([vector], 1)[0]


def embedding_status(config: CopilotConfig, *, environment: str | None = None) -> dict:
    """Non-secret embedding status for display: provider, model, version, dimensions, quality mode, degradation.

    Quality mode is SEMANTIC only when a real semantic provider will be used; the
    local hash embedder is reported as OFFLINE LEXICAL — never as "semantic".
    Never returns key contents. 02B adds ``version``, ``dimensions``, ``degraded`` (a lexical result that was not explicitly chosen),
    ``approved_for_environment`` and the problem codes, additively (existing keys are unchanged).
    """
    plan = resolve_embedding_plan(config, environment=environment)
    return {
        "provider": plan.provider,
        "configured_provider": plan.configured_provider,
        "model": plan.model if plan.semantic else "local-hash-v1",
        "base_url": (config.base_url if plan.provider == "openrouter" else config.embedding_base_url) if plan.semantic else None,
        "quality_mode": plan.quality_mode,
        "version": plan.version,
        "dimensions": plan.dimensions,
        "degraded": (not plan.semantic) and plan.configured_provider != "local",
        "label": plan.label,
        "environment": plan.environment,
        "approved_for_environment": plan.approved,
        "problems": list(plan.problems),
    }


def build_embedder(
    config: CopilotConfig,
    *,
    embeddings_cls: Any | None = None,
    environment: str | None = None,
) -> BaseEmbedder:
    """Return an embedder chosen from ``config.embedding_provider`` under the explicit 02B rules.

    - ``"local"``: the offline hashing embedder (development only; refused when hosted).
    - ``"openai"``: the OpenAI-compatible embedder (raises if no key).
    - ``"openrouter"``: OpenRouter's embeddings endpoint (``COPILOT_EMBEDDING_MODEL`` is a required ``vendor/model`` id, the key is
      ``OPENROUTER_API_KEY``); every request goes through the 05C governor chokepoint and is refused without an open governor.
    - ``"auto"`` (default): OpenAI only when a DEDICATED embedding key
      (``COPILOT_EMBEDDING_API_KEY``) is set, otherwise the local embedder in
      development. The chat ``OPENROUTER_API_KEY`` is NOT used as an embedding
      key: OpenRouter does not serve OpenAI's embeddings endpoint.

    HOSTED environments (staging, production, unknown ``API_ENV``) raise :class:`EmbeddingConfigurationError` instead of returning the hash
    embedder or an embedder with unknown dimensions.
    """
    plan = resolve_embedding_plan(config, environment=environment)
    if plan.problems:
        raise EmbeddingConfigurationError(list(plan.problems), environment=plan.environment, fields=plan.problem_fields)
    if plan.provider == "openrouter":
        from src.copilot.openrouter_embeddings import OpenRouterEmbedder

        return OpenRouterEmbedder(config)
    if plan.semantic:
        return OpenAIEmbedder(config, embeddings_cls=embeddings_cls)
    return LocalHashEmbedder()
