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

# 05E: audit and incident context is allow-list enforced (src/audit_allowlist.py). In tests and evaluators an unlisted key RAISES at the call site (so a new free-text key
# fails the suite); outside them the offending entry is dropped and never stored.
os.environ["AUDIT_CONTEXT_STRICT"] = "1"

_SCRUB_PREFIXES = (
    "OPENROUTER_", "ADZUNA_", "GOOGLE_", "BREVO_", "LANGFUSE_", "GEMINI_", "FEATURE_GOOGLE_LOGIN",
    "AGENT_CHECKPOINT_DATABASE_URL", "AGENT_EXTERNAL_OBSERVABILITY", "EMAIL_", "REDIS_", "RATE_LIMIT_",
    "DOCUMENT_STORAGE_DIR", "COPILOT_", "AI_BUDGET_",
)

if not _ALLOW_DEV:
    for _key in [k for k in os.environ if k.startswith(_SCRUB_PREFIXES)]:
        del os.environ[_key]
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_ROOT / 'ask4mo_test.db'}"
    os.environ["EMAIL_PROVIDER"] = "memory"
    # CI performance (W12.4F hotfix): measured, bcrypt at the product default of 12 rounds costs ~0.16 s per hash or verify locally (about 0.4 s on a CI runner) and the
    # suite registers and signs in thousands of users. 10 is the lowest value the product accepts (``src.authsec.passwords._default_rounds`` floors at 10), through the
    # product's own BCRYPT_ROUNDS setting; the algorithm, salting and verification are unchanged. The production default stays 12 (asserted in tests/test_auth_primitives.py).
    os.environ.setdefault("BCRYPT_ROUNDS", "10")
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

    def _is_isolated_pg_test_database(parsed) -> bool:
        """The ONE sanctioned non-SQLite target (W12.4D-P5-B): a database named ``p5b_*`` on the loopback PostgreSQL server that the test run itself created and
        announced through ``P5B_PG_ADMIN_URL`` (same host and port). Anything else (a developer or hosted PostgreSQL) is still refused."""
        admin = os.environ.get("P5B_PG_ADMIN_URL")
        if not admin:
            return False
        a = sqlalchemy.engine.make_url(admin)
        return (parsed.host in ("127.0.0.1", "localhost", "::1") and a.host == parsed.host and a.port == parsed.port and bool(parsed.database)
                and str(parsed.database).startswith("p5b_"))

    def _check_test_url(url) -> None:
        parsed = sqlalchemy.engine.make_url(url)
        if parsed.drivername.startswith("postgresql") and _is_isolated_pg_test_database(parsed):
            return
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


def install_research_cache_isolation() -> None:
    """Redirect the external-research cache (``data/cache/external`` by default) to a per-process temp directory.

    Idempotent. It runs when this module is IMPORTED (so a standalone evaluator that does ``import tests.conftest`` is isolated exactly like a
    pytest run: before P10D only the pytest fixture below did it, so an evaluator that exercised the research service read stale entries from, and
    wrote new ones into, the developer's cache) and again from the session fixture. The production cache code and default path are untouched.
    """
    if _ALLOW_DEV:
        return
    from src.copilot.research import cache

    if getattr(cache, "_ask4mo_isolated", False):
        return
    orig_read, orig_write = cache.read, cache.write
    directory = _TMP_ROOT / "research_cache"

    def read(key, **kwargs):
        kwargs.setdefault("cache_dir", directory)
        return orig_read(key, **kwargs)

    def write(key, payload, **kwargs):
        kwargs.setdefault("cache_dir", directory)
        return orig_write(key, payload, **kwargs)

    cache.read, cache.write = read, write
    cache._ask4mo_isolated = True
    cache._ask4mo_originals = (orig_read, orig_write)


if not _ALLOW_DEV:
    install_research_cache_isolation()


@pytest.fixture(scope="session", autouse=True)
def _isolate_research_cache():
    """The external-research cache defaults to ``data/cache/external``, which made one test write - and potentially READ stale entries from - the
    developer's cache. It is redirected to the temp directory when this module is imported (see ``install_research_cache_isolation``)."""
    install_research_cache_isolation()
    yield


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


# The test-client cookie-precedence compatibility fix lives in tests/_client_compat.py and is installed when the ``tests`` package is imported (pytest and the
# evaluators that import tests.* helpers alike). See that module and tests/test_testclient_cookie_precedence.py.


@pytest.fixture(autouse=True)
def _isolate_process_budget_governor():
    """Hosted app construction now installs a fail-closed process-wide guard.

    One test's application must not govern another test's isolated store/transport.
    Runtime behavior is unchanged; this boundary exists only in pytest.
    """
    from src.llm.budget.governor import uninstall

    uninstall()
    yield
    uninstall()
