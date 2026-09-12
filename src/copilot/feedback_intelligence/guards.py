"""Capability + filesystem guards for the offline Feedback Intelligence workflow (Phase 7G).

Feedback Intelligence has READ access to approved safe signal sources and WRITE access ONLY to its
own analysis-output root. It has NO capability for code/prompt/KB/config/Git/GitHub writes, no
shell execution, no arbitrary network, and it never executes external research (§37/§39/§77/§78).
These guards enforce the write boundary at runtime; the architectural test proves the package
imports none of the forbidden capabilities.
"""

from __future__ import annotations

from pathlib import Path

# The ONLY directories Feedback Intelligence may write to (§38).
ALLOWED_OUTPUT_ROOTS = ("evaluations/feedback_intelligence", "data/feedback_intelligence")


class OutputBoundaryError(RuntimeError):
    """Raised when a write is attempted outside the allowed analysis-output root."""


def safe_output_path(path: str | Path) -> Path:
    """Resolve ``path`` and confirm it is inside an allowed output root. Raise otherwise (§38)."""
    resolved = Path(path).resolve()
    roots = [Path(r).resolve() for r in ALLOWED_OUTPUT_ROOTS]
    if not any(_is_within(resolved, root) for root in roots):
        raise OutputBoundaryError(
            "Feedback Intelligence may only write under "
            f"{', '.join(ALLOWED_OUTPUT_ROOTS)} (attempted: {path}).")
    return resolved


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def capability_manifest() -> dict:
    """A declarative statement of what this workflow can and cannot do (for the audit/test)."""
    return {
        "read": ["approved local signal artifacts (evaluation JSON, structured feedback rows)"],
        "write": list(ALLOWED_OUTPUT_ROOTS),
        "forbidden": [
            "code writes (src/, app.py, frontend/)", "prompt writes", "agent tool registry writes",
            "knowledge/chroma/normalized writes", "production config writes", "git", "github",
            "shell execution", "arbitrary network", "external research execution",
            "candidate data access", "free-text user feedback ingestion",
        ],
        "network_default": "off",
        "self_modification": "none",
    }
