"""Free OpenRouter availability probe (05C, M-OR-KEY / J-OPENROUTER).

``probe_models`` lists the model ids the configured key can see through OpenRouter's models listing (``GET /api/v1/models``) and, where the API says so, which of them are
EMBEDDINGS-capable (``GET /api/v1/embeddings/models``, and an ``embeddings`` output modality in a model's architecture). These are metadata requests: no completion is requested, no
token is consumed and nothing is charged. The function takes an injectable ``httpx.Client`` so tests use a mocked transport; the command-line wrapper is ``scripts/openrouter_models_probe.py``
and is NEVER run by tests or CI.

The key is read through the secret seam, used only as a Bearer header and NEVER printed, logged, returned or included in an error: only the fixed word ``present`` or ``absent`` is reported.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

import httpx

from src.core.secrets import read_secret

BASE_URL_DEFAULT = "https://openrouter.ai/api/v1"
KEY_NAME = "OPENROUTER_API_KEY"


def key_status() -> str:
    """``present`` or ``absent``; the value itself is never exposed."""
    secret = read_secret(KEY_NAME)
    return "present" if secret is not None and secret.get_secret_value().strip() else "absent"


def _ids(payload: Any) -> list[dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    return [m for m in data if isinstance(m, dict) and isinstance(m.get("id"), str)] if isinstance(data, list) else []


def _says_embeddings(model: dict) -> bool:
    arch = model.get("architecture") if isinstance(model.get("architecture"), dict) else {}
    outputs = arch.get("output_modalities")
    if isinstance(outputs, list) and any(str(o).lower() == "embeddings" for o in outputs):
        return True
    modality = arch.get("modality")
    return isinstance(modality, str) and modality.lower().rstrip().endswith("embeddings")


def probe_models(*, client: httpx.Client | None = None, base_url: str | None = None, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return ``{key, ok, error, models: [{id, embeddings_capable}], counts}``. No key present means NO request is made."""
    out: dict[str, Any] = {"key": key_status(), "ok": False, "error": None, "models": [], "embeddings_listing": "not_requested", "tokens_consumed": 0}
    if out["key"] != "present":
        out["error"] = "key_absent"
        return out
    env = os.environ if environ is None else environ
    base = (base_url or env.get("OPENROUTER_BASE_URL") or BASE_URL_DEFAULT).rstrip("/")
    secret = read_secret(KEY_NAME)
    headers = {"Authorization": f"Bearer {secret.get_secret_value().strip()}"} if secret else {}   # type: ignore[union-attr]
    own = client is None
    http = client or httpx.Client(timeout=20.0)
    try:
        try:
            r = http.get(f"{base}/models", headers=headers)
        except httpx.HTTPError as exc:
            out["error"] = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
            return out
        if r.status_code in (401, 403):
            out["error"] = "key_rejected"
            return out
        if r.status_code != 200:
            out["error"] = f"http_{r.status_code}"
            return out
        try:
            models = _ids(r.json())
        except ValueError:
            out["error"] = "malformed_response"
            return out
        embedding_ids: set[str] = set()
        try:
            e = http.get(f"{base}/embeddings/models", headers=headers)
            if e.status_code == 200:
                embedding_ids = {m["id"] for m in _ids(e.json())}
                out["embeddings_listing"] = "available"
            else:
                out["embeddings_listing"] = f"http_{e.status_code}"
        except (httpx.HTTPError, ValueError):
            out["embeddings_listing"] = "unavailable"
        by_id = {m["id"]: m for m in models}
        for mid in embedding_ids:
            by_id.setdefault(mid, {"id": mid})
        out["models"] = sorted(({"id": mid, "embeddings_capable": mid in embedding_ids or _says_embeddings(m)} for mid, m in by_id.items()), key=lambda x: x["id"])
        out["ok"] = True
        out["counts"] = {"models": len(out["models"]), "embeddings_capable": sum(1 for m in out["models"] if m["embeddings_capable"])}
        return out
    finally:
        if own:
            http.close()


def compare_with_pricing(result: Mapping[str, Any], priced_models: list[str]) -> dict[str, list[str]]:
    """Which models of the budget price table the key can / cannot see (ids only)."""
    seen = {m["id"] for m in result.get("models", [])}
    return {"priced_and_available": sorted(m for m in priced_models if m in seen), "priced_but_not_listed": sorted(m for m in priced_models if m not in seen)}
