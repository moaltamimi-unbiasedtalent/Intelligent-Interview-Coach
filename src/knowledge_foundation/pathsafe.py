"""Protected-output validation shared by the knowledge-foundation scripts. An output path is rejected when it RESOLVES (symlinks, ``..`` and relative paths followed; the file need
not exist) inside a protected directory of the repository root. Validation happens before any local data is read."""

from __future__ import annotations

from pathlib import Path

__all__ = ["PROTECTED_DIRECTORIES", "output_is_protected"]

PROTECTED_DIRECTORIES = ("data", "evaluations")


def output_is_protected(out: str | Path, root: Path) -> bool:
    base = Path(root).resolve()
    target = Path(out)
    resolved = (target if target.is_absolute() else Path.cwd() / target).resolve()
    rel = (base / target).resolve() if not target.is_absolute() else resolved          # a relative path is also judged against the repository root
    return any(candidate == (base / d).resolve() or (base / d).resolve() in candidate.parents for candidate in (resolved, rel) for d in PROTECTED_DIRECTORIES)
