"""Production prompt access (package 01B, REVIEW-02 R1, R2, R5, R6, R7).

The one place the application resolves versioned prompt assets from ``prompts/`` through the
01B0 contract (``src/prompt_loader.py``). Consumers never read the files themselves:

* ``render(family, consumer, **variables)``   rendered text (equals ``str.format`` of the body).
* ``template(family, consumer)``              the unrendered body (for a module constant that
                                              callers still ``.format`` themselves).
* ``table(family, consumer)``                 a ``key: value`` lookup asset as a dict.
* ``effective_versions(families)``            ``{family: {"version", "sha256"}}`` for attribution.

Behaviour guarantees
--------------------
* Fail closed: the whole tree is validated eagerly when first used (schema, placeholder and
  integrity-hash checks). A missing/invalid asset raises a ``PromptError`` subclass naming the
  family; there is deliberately NO silent fallback to a literal in code.
* Each consumer passes its own contract id (for example ``"agent.policies"``) and the asset must
  declare it in ``compatible_with`` or ``IncompatiblePrompt`` is raised.
* The loader is created once per process: the effective version is fixed for the process lifetime,
  so the version recorded on a run is always the one that produced its text. Rollback to an earlier
  approved version is an edit of ``prompts/current.json`` (a reviewed change to a repository file,
  shipped with the image); it takes effect on the next process start and needs no code change.
* Read-only and offline: no network, provider or database access, no write path, no environment
  override of the asset root.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path

from src.prompt_loader import FilePromptLoader, PromptAsset

__all__ = [
    "PROMPT_ROOT", "get_loader", "asset", "render", "template", "table", "effective_versions",
    "prompt_set_version", "parse_table", "reload_for_tests",
]

# prompts/ sits next to src/ in the repository and in the Docker image (deploy/Dockerfile.api).
PROMPT_ROOT = Path(__file__).resolve().parent.parent / "prompts"

_root: Path = PROMPT_ROOT


@lru_cache(maxsize=1)
def _cached_loader() -> FilePromptLoader:
    return FilePromptLoader(_root)


def get_loader() -> FilePromptLoader:
    """The process-wide validated loader (raises a ``PromptError`` if the tree is invalid)."""
    return _cached_loader()


def reload_for_tests(root: Path | str | None = None) -> None:
    """Test seam: drop the cached loader and optionally point it at another asset tree."""
    global _root
    _root = Path(root) if root is not None else PROMPT_ROOT
    _cached_loader.cache_clear()


def asset(family: str, consumer: str) -> PromptAsset:
    """Resolve the current approved asset of ``family`` and check consumer compatibility."""
    resolved = get_loader().resolve(family)
    resolved.check_compatible(consumer)
    return resolved


def render(family: str, consumer: str, **variables: object) -> str:
    """Render ``family`` with exactly its declared variables (byte-equal to ``str.format``)."""
    return get_loader().render(asset(family, consumer), variables)


def template(family: str, consumer: str) -> str:
    """The unrendered body of ``family`` (placeholders and ``{{ }}`` escapes intact)."""
    return asset(family, consumer).body


def parse_table(body: str) -> dict[str, str]:
    """Parse a ``key: value`` lookup body (one entry per line, keys unique)."""
    out: dict[str, str] = {}
    for line in body.split("\n"):
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not key or key in out:
            raise ValueError(f"malformed or duplicate table line: {line[:40]!r}")
        out[key] = value.strip()
    return out


def table(family: str, consumer: str) -> dict[str, str]:
    """A lookup-table asset (no placeholders) as a ``dict``."""
    return parse_table(render(family, consumer))


def effective_versions(families: Iterable[str] | None = None) -> dict[str, dict[str, str]]:
    """Declared version plus body hash for the current asset of each family (default: all).

    Safe metadata: identifiers and hashes only, never prompt text.
    """
    loader = get_loader()
    wanted = sorted(set(families)) if families is not None else loader.families()
    out: dict[str, dict[str, str]] = {}
    for family in wanted:
        resolved = loader.resolve(family)
        out[family] = {"version": resolved.version, "sha256": resolved.sha256}
    return out


def prompt_set_version(versions: Mapping[str, Mapping[str, str]] | None = None) -> str:
    """One short id for a whole set of prompt versions (a hash of ``family@version#sha``)."""
    versions = versions if versions is not None else effective_versions()
    canon = ";".join(f"{f}@{v['version']}#{v['sha256']}" for f, v in sorted(versions.items()))
    return "promptset-" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]
