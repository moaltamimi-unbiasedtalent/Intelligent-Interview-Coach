"""OpenRouter embedding model facts used ONLY for safety checks, and the offline model-listing check (02B, OD-EMBED provisional).

This is NOT a model choice. Which embedding model serves production is decided from measured benchmark evidence and is configuration
(``COPILOT_EMBEDDING_MODEL``); nothing here selects, defaults or prefers a model. The table below holds the few facts the adapter uses to
refuse an unsafe configuration BEFORE any paid call:

* ``native_dimensions``: the model's documented output size. A configured ``dimensions`` that cannot be honoured is refused.
* ``context_tokens``: the model's input context (public listing data recorded in
  ``docs/production/execution/evidence/OPENROUTER_EMBEDDING_AVAILABILITY_2026-10-22.md``). An input estimated above it is refused, never truncated.
* ``supports_dimensions``: whether the model accepts the endpoint's optional ``dimensions`` parameter (truncation). Only the OpenAI v3 models are
  marked, per the upstream model's own documentation; the OpenRouter contract allows the parameter but a model that ignores it is caught by the
  response-length check, never trusted.

THESE VALUES ARE EXPECTATIONS, NOT MEASUREMENTS: the dimensions an OpenRouter route actually returns have not been verified live. A model
not listed here is allowed only with an explicit ``COPILOT_EMBEDDING_DIMENSIONS`` and is then validated against every response.

``check_model_in_listing`` is the no-network check: it reads a RECORDED listing (the output of ``scripts/openrouter_models_probe.py`` or a saved
``GET /api/v1/models?output_modalities=embeddings`` / ``/api/v1/embeddings/models`` body) and confirms the configured id is an embeddings model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = ["ModelFacts", "KNOWN_OPENROUTER_EMBEDDING_FACTS", "facts_for", "check_model_in_listing", "listing_embedding_ids"]


@dataclass(frozen=True)
class ModelFacts:
    native_dimensions: int
    context_tokens: int
    supports_dimensions: bool = False


KNOWN_OPENROUTER_EMBEDDING_FACTS: Mapping[str, ModelFacts] = {
    "openai/text-embedding-3-large": ModelFacts(3072, 8192, True),
    "openai/text-embedding-3-small": ModelFacts(1536, 8192, True),
    "baai/bge-m3": ModelFacts(1024, 8194, False),
    "intfloat/multilingual-e5-large": ModelFacts(1024, 512, False),
}


def facts_for(model: str) -> ModelFacts | None:
    return KNOWN_OPENROUTER_EMBEDDING_FACTS.get(str(model))


def _says_embeddings(model: Mapping[str, Any]) -> bool:
    arch = model.get("architecture") if isinstance(model.get("architecture"), dict) else {}
    outs = arch.get("output_modalities")
    if isinstance(outs, list) and any(str(o).lower() == "embeddings" for o in outs):
        return True
    modality = arch.get("modality")
    return isinstance(modality, str) and modality.lower().rstrip().endswith("embeddings")


def listing_embedding_ids(listing: Any) -> tuple[set[str], set[str]]:
    """``(all listed ids, ids the listing marks embeddings-capable)`` from either a 05C probe result (``models`` with ``embeddings_capable``)
    or a raw OpenRouter body (``data``). Anything unreadable yields empty sets (never a guess)."""
    seen: set[str] = set()
    capable: set[str] = set()
    if not isinstance(listing, dict):
        return seen, capable
    rows = listing.get("models") if isinstance(listing.get("models"), list) else listing.get("data")
    for m in rows if isinstance(rows, list) else []:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            continue
        seen.add(m["id"])
        if m.get("embeddings_capable") is True or _says_embeddings(m):
            capable.add(m["id"])
    return seen, capable


def check_model_in_listing(model: str, listing: Any, *, embeddings_listing: bool = False) -> dict[str, Any]:
    """Offline validation of a configured model id against a recorded listing. ``embeddings_listing=True`` declares that ``listing`` came from the
    embeddings-only endpoint (every row is an embeddings model). Result codes: ``ok``, ``listing_unreadable``, ``model_not_listed``,
    ``not_an_embeddings_model``. No network, no key, no side effect."""
    seen, capable = listing_embedding_ids(listing)
    if embeddings_listing:
        capable = set(seen)
    facts = facts_for(model)
    out: dict[str, Any] = {"model": model, "listed": model in seen, "embeddings_capable": model in capable, "known_facts": facts is not None,
                           "native_dimensions": facts.native_dimensions if facts else None, "context_tokens": facts.context_tokens if facts else None}
    if not seen:
        out.update(ok=False, code="listing_unreadable")
    elif model not in seen:
        out.update(ok=False, code="model_not_listed")
    elif model not in capable:
        out.update(ok=False, code="not_an_embeddings_model")
    else:
        out.update(ok=True, code="ok")
    return out
