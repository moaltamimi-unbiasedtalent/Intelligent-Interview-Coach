"""Shared pytest fixtures and the TEST-ISOLATION boundary (Capstone P8; hardened in P10B-W9.12).

Deterministic tests must never depend on, or write to, a developer's environment. Importing this file (pytest
does so before any test module imports ``src``) therefore:

1. disables ``.env`` loading (``PYTHON_DOTENV_DISABLED`` and a no-op ``dotenv.load_dotenv``), so a developer's
   local ``OPENROUTER_MODEL_*`` / API keys can never leak into a test (this was the root cause of the 13
   ``.env``-dependent backend failures: ``load_config()`` calls ``load_dotenv`` and pollutes ``os.environ`` for
   every later test);
2. scrubs provider / persistence variables inherited from the shell;
3. points ``DATABASE_URL`` (and so the derived agent-checkpoint file) at a per-process temp directory;
3b. points Streamlit's ``st.secrets`` at an empty file (it would otherwise read the developer's
   ``.streamlit/secrets.toml`` and export those keys into ``os.environ``);
4. forbids any SQLAlchemy engine that is not in-memory or inside the system temp directory (so the normal
   development database ``data/interview_studio.db`` - or any configured non-test database - can never be written;
   a test that tries fails immediately with a clear message);
5. fingerprints the development stores before the run and FAILS the session if any of them changed.

Opt out deliberately (never in CI) with ``ASK4MO_TEST_ALLOW_DEV_PERSISTENCE=1``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_ALLOW_DEV = os.environ.get("ASK4MO_TEST_ALLOW_DEV_PERSISTENCE") == "1"
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ask4mo_pytest_")).resolve()
_SYSTEM_TMP = Path(tempfile.gettempdir()).resolve()

_SCRUB_PREFIXES = (
    "OPENROUTER_", "ADZUNA_", "GOOGLE_", "BREVO_", "LANGFUSE_", "GEMINI_", "FEATURE_GOOGLE_LOGIN",
    "AGENT_CHECKPOINT_DATABASE_URL", "AGENT_EXTERNAL_OBSERVABILITY", "EMAIL_", "REDIS_", "RATE_LIMIT_BACKEND",
    "DOCUMENT_STORAGE_DIR", "COPILOT_",
)

if not _ALLOW_DEV:
    for _key in [k for k in os.environ if k.startswith(_SCRUB_PREFIXES)]:
        del os.environ[_key]
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'ask4mo_test.db'}"
    os.environ["EMAIL_PROVIDER"] = "memory"
    # The default vector-store directory is ``data/chroma`` (relative to the cwd). On a fresh clone (CI) opening it CREATES
    # ``data/chroma/chroma.sqlite3``; locally the pre-built store hid that write. Point it at the temp dir.
    os.environ["COPILOT_CHROMA_DIR"] = str(_TMP_ROOT / "chroma")

    try:  # belt and braces for python-dotenv versions that ignore PYTHON_DOTENV_DISABLED
        import dotenv
        import dotenv.main

        def _no_dotenv(*_a, **_k):
            return False

        dotenv.load_dotenv = _no_dotenv
        dotenv.main.load_dotenv = _no_dotenv
    except Exception:  # pragma: no cover - dotenv is a hard dependency; never block collection
        pass

    try:
        # Streamlit's st.secrets reads the developer's local .streamlit/secrets.toml and EXPORTS every top-level
        # key into os.environ on first access (a second path by which local keys leaked into tests). Point it at an
        # empty file for the whole run.
        import streamlit.config as _st_config

        _empty_secrets = _TMP_ROOT / "empty_secrets.toml"
        _empty_secrets.write_text("", encoding="utf-8")
        _st_config.set_option("secrets.files", [str(_empty_secrets)])
    except Exception:  # pragma: no cover - streamlit is a hard dependency; never block collection
        pass

    import sqlalchemy
    import sqlalchemy.engine

    _real_create_engine = sqlalchemy.create_engine

    def _check_test_url(url) -> None:
        parsed = sqlalchemy.engine.make_url(url)
        if not parsed.drivername.startswith("sqlite"):
            raise RuntimeError(
                f"Test isolation: refusing non-sqlite database URL ({parsed.drivername}). "
                "Deterministic tests may only use in-memory or temp-directory SQLite.")
        db = parsed.database
        if db in (None, "", ":memory:") or str(db).startswith("file::memory:"):
            return
        resolved = Path(db).expanduser()
        if not resolved.is_absolute():
            resolved = Path.cwd() / resolved
        resolved = resolved.resolve()
        if _SYSTEM_TMP not in resolved.parents and _TMP_ROOT not in resolved.parents:
            raise RuntimeError(
                f"Test isolation: refusing to open database {resolved}. Tests must use an in-memory or "
                f"temp-directory SQLite database, never the development store (set "
                f"ASK4MO_TEST_ALLOW_DEV_PERSISTENCE=1 only for a deliberate local experiment).")

    def _guarded_create_engine(url, *args, **kwargs):
        _check_test_url(url)
        return _real_create_engine(url, *args, **kwargs)

    sqlalchemy.create_engine = _guarded_create_engine
    sqlalchemy.engine.create_engine = _guarded_create_engine

    try:  # same fail-fast rule for the vector store: only temp-directory Chroma persistence is allowed in tests
        import chromadb

        _real_persistent_client = chromadb.PersistentClient

        def _guarded_persistent_client(path=None, *args, **kwargs):
            resolved = (Path(path) if path else Path("chroma")).expanduser()
            resolved = (resolved if resolved.is_absolute() else Path.cwd() / resolved).resolve()
            if _SYSTEM_TMP not in resolved.parents and _TMP_ROOT not in resolved.parents:
                raise RuntimeError(
                    f"Test isolation: refusing to open the vector store at {resolved}. Tests must use a "
                    "temp-directory Chroma path (COPILOT_CHROMA_DIR is redirected there by tests/conftest.py).")
            return _real_persistent_client(path, *args, **kwargs)

        chromadb.PersistentClient = _guarded_persistent_client
    except Exception:  # pragma: no cover - chromadb is a hard dependency; never block collection
        pass


def _fingerprint_dev_stores() -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) of the persistent development stores a test must never modify."""
    out: dict[str, tuple[int, int]] = {}
    data = _ROOT / "data"
    candidates = list(data.glob("*.db")) + list(data.glob("*.sqlite*")) + list(data.glob("*.db-*"))
    for sub in ("chroma", "cache", "knowledge", "feedback_intelligence"):
        d = data / sub
        if d.exists():
            candidates += [p for p in d.rglob("*") if p.is_file()]
    for p in candidates:
        try:
            st = p.stat()
        except OSError:
            continue
        out[str(p.relative_to(_ROOT))] = (st.st_size, st.st_mtime_ns)
    return out


_DEV_BEFORE = {} if _ALLOW_DEV else _fingerprint_dev_stores()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_ROOT, ignore_errors=True)
    if _ALLOW_DEV:
        return
    after = _fingerprint_dev_stores()
    changed = sorted(k for k in set(_DEV_BEFORE) | set(after) if _DEV_BEFORE.get(k) != after.get(k))
    if changed:
        print("\nTEST ISOLATION VIOLATION: the test run modified development stores: " + ", ".join(changed))
        session.exitstatus = 1


@pytest.fixture(scope="session", autouse=True)
def _isolate_research_cache():
    """The external-research cache defaults to ``data/cache/external`` (relative to the cwd), which made one test
    write - and potentially READ stale entries from - the developer's cache. Default it to the temp directory."""
    if _ALLOW_DEV:
        yield
        return
    from src.copilot.research import cache

    orig_read, orig_write = cache.read, cache.write
    directory = _TMP_ROOT / "research_cache"

    def read(key, **kwargs):
        kwargs.setdefault("cache_dir", directory)
        return orig_read(key, **kwargs)

    def write(key, payload, **kwargs):
        kwargs.setdefault("cache_dir", directory)
        return orig_write(key, payload, **kwargs)

    cache.read, cache.write = read, write
    try:
        yield
    finally:
        cache.read, cache.write = orig_read, orig_write


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    # Fresh rate-limit counters per test (the in-memory limiter is a process singleton).
    from src.api.rate_limit import reset_rate_limiter

    reset_rate_limiter()
    yield
    # W10.11: durable pause/flag accessors installed by one test's repository must never leak into the next.
    from src.application import pause as _pause
    from src.platform_config import flags as _flags

    _pause.uninstall()
    _flags.uninstall()
    from src.reporting import telemetry as _telemetry

    _telemetry.uninstall()
    # W10.7: a governed AI configuration activated by one test must never route the model registry in the next.
    from src.ai_admin.resolver import uninstall_resolver

    uninstall_resolver()
