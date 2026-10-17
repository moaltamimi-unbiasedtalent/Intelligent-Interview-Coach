"""Native occupation codes are STRINGS (GKB-3/GKB-4). ISCO-08 identifies the Armed Forces group with leading zeros (``0110``, ``0210``, ``0310``); the legacy stores kept the codes
stripped (``110``). The authoritative identity is the padded official code and the stripped value stays traceable as a legacy key.

``restore_isco_zero_padding`` restores padding ONLY when the stripped value is not itself an official code, exactly one zero-padded variant exists in the authority (the caller's
lookup, for example the persisted ISCO-08 graph) and that variant lies in major group 0 (the only group whose codes begin with zero). Otherwise it reports why it did not: nothing
is invented, and an ambiguous or absent padding is never guessed."""

from __future__ import annotations

from typing import Callable

__all__ = ["normalize_native_code", "restore_isco_zero_padding", "isco_padding_candidates"]


def normalize_native_code(scheme: str, raw: str | None) -> str | None:
    """Trim whitespace only; never convert to a number and never strip zeros. Format validation belongs to the taxonomy's registered code pattern."""
    if raw is None:
        return None
    return str(raw).strip()


def isco_padding_candidates(raw: str) -> list[str]:
    """Longer zero-padded variants of a stripped ISCO value (all lie in major group 0)."""
    if not raw.isdigit() or not (1 <= len(raw) <= 4) or raw.startswith("0"):
        return []
    return [raw.zfill(n) for n in range(len(raw) + 1, 5)]


def restore_isco_zero_padding(raw: str | None, exists: Callable[[str], bool]) -> tuple[str | None, str]:
    code = normalize_native_code("isco", raw)
    if not code or not code.isdigit() or not (1 <= len(code) <= 4):
        return None, "invalid_format"
    if exists(code):
        return code, "exact"
    found = [c for c in isco_padding_candidates(code) if exists(c)]
    if len(found) == 1:
        return found[0], "zero_padding_restored"
    return None, "ambiguous_padding" if len(found) > 1 else "not_found"
