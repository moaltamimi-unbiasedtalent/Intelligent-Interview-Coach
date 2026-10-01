"""P10B-W9.12 (TD-W9-02) - the deterministic suite cannot touch a developer's environment or persistence.

These tests exercise the guard in tests/conftest.py: `.env` is never loaded, provider/model variables are
scrubbed, the configured database is a temp file, and any attempt to open the development database (or any
non-temp / non-sqlite store) fails immediately instead of writing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import sqlalchemy

ROOT = Path(__file__).resolve().parent.parent
ALLOW_DEV = os.environ.get("ASK4MO_TEST_ALLOW_DEV_PERSISTENCE") == "1"
pytestmark = pytest.mark.skipif(ALLOW_DEV, reason="deliberate local opt-out of the isolation guard")


def test_database_url_is_a_temp_file_never_the_dev_database():
    url = sqlalchemy.engine.make_url(os.environ["DATABASE_URL"])
    path = Path(url.database).resolve()
    assert Path(tempfile.gettempdir()).resolve() in path.parents
    assert ROOT / "data" not in path.parents


def test_provider_and_model_variables_are_scrubbed_from_the_environment():
    leaked = [k for k in os.environ if k.startswith(("OPENROUTER_", "ADZUNA_", "BREVO_", "LANGFUSE_"))]
    assert leaked == []
    assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1"


def test_loading_config_never_reads_a_dotenv_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENROUTER_MODEL_FAST=evil/model\nOPENROUTER_API_KEY=sk-evil\n")
    monkeypatch.chdir(tmp_path)
    from src.config import load_config

    load_config()
    assert "OPENROUTER_MODEL_FAST" not in os.environ
    assert "OPENROUTER_API_KEY" not in os.environ


def test_opening_the_development_database_is_refused():
    dev = ROOT / "data" / "interview_studio.db"
    with pytest.raises(RuntimeError, match="Test isolation"):
        sqlalchemy.create_engine(f"sqlite:///{dev}")
    with pytest.raises(RuntimeError, match="Test isolation"):
        sqlalchemy.create_engine("sqlite:///data/interview_studio.db")  # the relative default
    with pytest.raises(RuntimeError, match="Test isolation"):
        sqlalchemy.create_engine("postgresql://user:pw@localhost/ask4mo")


def test_in_memory_and_temp_databases_are_allowed(tmp_path):
    sqlalchemy.create_engine("sqlite://").dispose()
    sqlalchemy.create_engine("sqlite:///:memory:").dispose()
    sqlalchemy.create_engine(f"sqlite:///{tmp_path / 'ok.db'}").dispose()


def test_research_cache_defaults_to_a_temp_directory(monkeypatch):
    from src.copilot.research import cache

    cache.write("w912-isolation-probe", {"x": 1})
    assert not (ROOT / "data" / "cache" / "external" / "w912-isolation-probe.json").exists()
    assert cache.read("w912-isolation-probe") == {"x": 1}


def test_streamlit_secrets_do_not_read_the_developers_local_secrets_file():
    import streamlit as st

    assert not st.secrets.get("OPENROUTER_API_KEY")          # never print or assert on a value
    assert "OPENROUTER_API_KEY" not in os.environ              # and st.secrets must not export keys into the env


def test_vector_store_is_redirected_to_temp_and_non_temp_paths_are_refused(tmp_path):
    import chromadb

    configured = Path(os.environ["COPILOT_CHROMA_DIR"]).resolve()
    assert ROOT / "data" not in configured.parents
    with pytest.raises(RuntimeError, match="Test isolation"):
        chromadb.PersistentClient(path=str(ROOT / "data" / "chroma"))
    chromadb.PersistentClient(path=str(tmp_path / "ok"))  # temp location is allowed
