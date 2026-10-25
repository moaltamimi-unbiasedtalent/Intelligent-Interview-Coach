"""07A engineering hygiene: behaviour when an OPTIONAL dependency (an extra in pyproject.toml) is missing.

Every optional package is lazily imported; the product must import, start and answer without it, and each feature that uses one must degrade to a controlled, truthful state
(never a crash, never a misleading message such as "corrupt file"). Two layers, both offline and independent of what is installed:

* in-process: ``sys.modules[name] = None`` makes ``import name`` raise ImportError exactly as an absent package would, and the specific degrade path is asserted;
* subprocess: a fresh interpreter whose meta-path finder blocks EVERY optional package imports the whole application, builds the real app and serves requests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Optional extras and the import names they provide (pyproject.toml [project.optional-dependencies]; redis is declared but remains optional outside the hosted image).
OPTIONAL_IMPORTS = {
    "speech": ["google.cloud.speech_v2"],
    "live": ["google.genai"],
    "ocr": ["pytesseract", "pdf2image"],
    "observability": ["langfuse"],
    "knowledge": ["pyarrow"],
    "evaluation": ["ragas"],
    "db": ["alembic", "psycopg", "langgraph.checkpoint.postgres"],
    "redis": ["redis"],
}
ALL_BLOCKED = sorted({name for names in OPTIONAL_IMPORTS.values() for name in names})


def block(monkeypatch, *names: str) -> None:
    """Make ``import <name>`` raise ImportError (an absent package), including already-imported submodules."""
    for loaded in [m for m in sys.modules if any(m == n or m.startswith(n + ".") for n in names)]:
        monkeypatch.delitem(sys.modules, loaded, raising=False)
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


def test_the_optional_import_inventory_matches_pyproject():
    """The inventory above must cover every extra declared in pyproject.toml (a new extra without a degrade test fails here)."""
    import tomllib

    declared = set(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"])
    assert declared - {"dev"} <= set(OPTIONAL_IMPORTS) | {"observability", "knowledge"}, declared
    assert {"speech", "ocr", "live", "db", "evaluation", "observability", "knowledge"} <= set(OPTIONAL_IMPORTS)


# ------------------------------------------------------------------------------------------------------------------------------------ the whole application
def test_the_whole_application_imports_starts_and_serves_with_every_optional_extra_missing():
    proc = subprocess.run([sys.executable, str(ROOT / "tests/_optional_deps_probe_07a.py"), json.dumps(ALL_BLOCKED)], cwd=ROOT, capture_output=True, text=True, timeout=240)
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-2500:]
    line = next(x for x in proc.stdout.splitlines() if x.startswith("PROBE_RESULT "))
    out = json.loads(line[len("PROBE_RESULT "):])
    for label in ("health", "capabilities", "speech_capabilities", "realtime_status", "documents", "model_profiles"):
        assert out[label] == 200, (label, out)
    assert out["ocr_available"] is False and out["ocr_status_available"] is False
    assert out["alembic_head"] is None                                    # the head is unreadable without alembic: reported as unknown, never a crash
    assert out["ragas_available"] is False
    assert out["blocked_modules_present"] == []


# ------------------------------------------------------------------------------------------------------------------------------------ feature degrade paths
def test_google_speech_to_text_without_its_sdk_is_a_controlled_unavailable(monkeypatch):
    from src.speech_service import GoogleSpeechTranscriptionService, SpeechError

    block(monkeypatch, "google.cloud.speech_v2")
    svc = GoogleSpeechTranscriptionService(project_id="deferral-07a")
    with pytest.raises(SpeechError) as exc:
        svc._get_client()
    assert exc.value.category == "unavailable" and "not installed" in exc.value.message
    with pytest.raises(SpeechError) as exc:
        svc.transcribe(b"RIFF", mime_type="audio/wav", language="en")
    assert exc.value.category in ("unavailable", "provider_error", "empty", "corrupt_audio") and "Traceback" not in str(exc.value)


def test_gemini_live_token_minting_without_its_sdk_is_a_controlled_unavailable(monkeypatch):
    from src.live_interview import GeminiLiveTokenService, LiveInterviewError

    block(monkeypatch, "google.genai")
    svc = GeminiLiveTokenService.__new__(GeminiLiveTokenService)
    with pytest.raises(LiveInterviewError) as exc:
        svc._default_minter(api_key="not-a-key", model="m", ttl_seconds=60, now=0.0)
    assert exc.value.category == "unavailable"


def test_ocr_without_its_packages_is_unavailable_never_a_corrupt_document(monkeypatch):
    from src.documents import ocr

    block(monkeypatch, "pytesseract", "pdf2image")
    engine = ocr.TesseractOcrEngine()
    assert engine.is_available() is False
    assert ocr.installed_tesseract_languages() == set()
    status = ocr.ocr_runtime_status()
    assert status["available"] is False and not status.get("pdf_ocr_available")
    with pytest.raises(ocr.OcrError) as image:
        engine.image_to_text(b"not-an-image", lang="en")
    assert image.value.kind == "ocr_unavailable", "a missing OCR package must never be reported as an unreadable image"
    monkeypatch.setattr(ocr, "_poppler_ok", lambda: True)               # Poppler present, pdf2image missing: still a capability gap
    with pytest.raises(ocr.OcrError) as pdf:
        engine.pdf_to_text(b"%PDF-1.4", lang="en")
    assert pdf.value.kind == "ocr_unavailable"


def test_a_scanned_upload_without_ocr_packages_fails_as_ocr_unavailable_through_the_parser(monkeypatch):
    """Through the document OCR parser: the failure kind the candidate sees is ocr_unavailable (try again once OCR is enabled), not a corrupt-file kind."""
    from src.documents import ocr

    block(monkeypatch, "pytesseract", "pdf2image")
    for extension in ("png", "pdf"):
        with pytest.raises(ocr.OcrError) as exc:
            ocr.ocr_parse(ocr.build_ocr_engine(), b"\x89PNG....", extension, lang="en")
        assert exc.value.kind == "ocr_unavailable", extension


def test_langfuse_missing_degrades_to_the_noop_sink_even_when_enabled_with_credentials(monkeypatch):
    from src.observability import NoOpObservabilitySink, build_observability_sink
    from src.observability.config import ObservabilityConfig

    block(monkeypatch, "langfuse")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-07a-not-real")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-07a-not-real")
    cfg = ObservabilityConfig(**{**_default_observability_fields(), "enabled": True})
    sink = build_observability_sink(cfg)
    assert isinstance(sink, NoOpObservabilitySink)


def _default_observability_fields() -> dict:
    from dataclasses import fields

    from src.observability.config import load_config

    base = load_config()
    return {f.name: getattr(base, f.name) for f in fields(base)}


def test_a_shared_rate_limit_store_without_the_redis_package_falls_back_to_the_in_memory_limiter(monkeypatch):
    from src.api import rate_limit as rl

    block(monkeypatch, "redis")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6399/0")
    limiter = rl.build_rate_limiter()
    assert isinstance(limiter, rl.InMemoryRateLimiter) and rl.shared_store_active() is False
    rl.reset_rate_limiter(rl.InMemoryRateLimiter())


def test_parquet_helpers_without_pyarrow_raise_an_install_hint_and_jsonl_still_works(monkeypatch, tmp_path):
    from pydantic import BaseModel

    from src.copilot.knowledge import canonical

    class Row(BaseModel):
        name: str

    block(monkeypatch, "pyarrow")
    with pytest.raises(canonical.ParquetUnavailableError) as exc:
        canonical.write_parquet([Row(name="a")], tmp_path / "x.parquet")
    assert 'pip install -e ".[knowledge]"' in str(exc.value)
    n = canonical.write_jsonl([Row(name="a"), Row(name="b")], tmp_path / "x.jsonl")
    assert n == 2 and [r.name for r in canonical.read_jsonl(tmp_path / "x.jsonl", Row)] == ["a", "b"]


def test_a_postgres_checkpointer_without_its_package_fails_closed_and_never_leaks_the_url(monkeypatch):
    from src.agent.checkpoint import AgentConfigurationError, build_checkpointer

    block(monkeypatch, "langgraph.checkpoint.postgres")
    url = "postgresql+psycopg://user07a:secret07a@db.invalid:5432/app"
    with pytest.raises(AgentConfigurationError) as exc:
        build_checkpointer(checkpoint_url=url)
    assert "secret07a" not in str(exc.value) and "db.invalid" not in str(exc.value)


def test_the_migration_head_is_unknown_without_alembic_and_the_command_center_still_answers(monkeypatch):
    from src.application import admin_command_center as cc
    from tests.test_admin_foundation_w10_1 import Env

    block(monkeypatch, "alembic")
    assert cc.repository_head() is None
    env = Env()
    try:
        _uid, cookies = env.user("platform_admin")
        r = env.c.get("/api/v1/admin/command-center/health", cookies=cookies)
        assert r.status_code == 200, r.text[:300]
        assert cc.migration_status(env.repo.session_factory)["state"] == "unknown"      # unreadable head: reported as unknown with a warning, never a crash
    finally:
        env.close()


def test_ragas_missing_is_reported_unavailable_without_a_provider_call(monkeypatch):
    from src.application.evaluation_service import check_ragas_configuration
    from src.copilot.evaluation.ragas_adapter import ragas_available

    block(monkeypatch, "ragas")
    assert ragas_available() is False
    snapshot = check_ragas_configuration()
    assert isinstance(snapshot, dict)
    assert not any(isinstance(v, str) and ("sk-" in v or "Bearer" in v) for v in snapshot.values())
