"""Version-independent Alembic head checks (shared by tests and the scripts/eval_*.py evaluators).

Why: tests used to hard-code the head revision name (and the number of migration files), so every package that added a migration had to edit ~40 files.
These helpers read the REAL script directory and assert the properties that actually matter, so adding a revision needs no edit here or in any caller:

* exactly ONE head, one base, a LINEAR chain from the base to the head (no branch, no merge point);
* every ``down_revision`` resolves to a revision that exists;
* revision numbers are contiguous from 0001 and the file count equals the highest number;
* each file name starts with its own ``revision`` id;
* the specific historical revisions a check cares about are in the chain.

``repository_head()`` parses the files itself (it does NOT call Alembic), so a test that upgrades a database to "head" or asks Alembic's ``ScriptDirectory`` for
its heads and compares with ``repository_head()`` compares two independent derivations and still bites.

Stdlib only. Every function takes an optional ``versions`` directory (default: the module-level ``VERSIONS``, resolved per call) so the negative tests can run on disposable copies.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"

_REV = re.compile(r"^revision(?:\s*:\s*[^=\n]+)?\s*=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN = re.compile(r"^down_revision(?:\s*:\s*[^=\n]+)?\s*=\s*(.+)$", re.M)


class MigrationChainError(AssertionError):
    """The migration history violates a structural property (an AssertionError so a test fails with the reason)."""


def _dir(versions: Path | None) -> Path:
    """Resolved at call time (not import time) so a test can monkeypatch ``VERSIONS`` and every caller, evaluators included, follows."""
    return Path(versions) if versions is not None else VERSIONS


def migration_files(versions: Path | None = None) -> list[Path]:
    return sorted(p for p in _dir(versions).glob("0*.py"))


def revisions(versions: Path | None = None) -> dict[str, tuple[tuple[str, ...], str]]:
    """revision id -> (down_revisions, file name), parsed from the files."""
    out: dict[str, tuple[tuple[str, ...], str]] = {}
    for p in migration_files(versions):
        text = p.read_text(encoding="utf-8")
        m, d = _REV.search(text), _DOWN.search(text)
        if not m or not d:
            raise MigrationChainError(f"{p.name}: no revision/down_revision declaration")
        if m.group(1) in out:
            raise MigrationChainError(f"duplicate revision id {m.group(1)}")
        out[m.group(1)] = (tuple(re.findall(r"['\"]([^'\"]+)['\"]", d.group(1))), p.name)
    return out


def number(revision_or_file: str) -> int:
    return int(revision_or_file.split("_", 1)[0])


def problems(versions: Path | None = None, require: tuple[str, ...] = ()) -> list[str]:
    """Every structural violation (empty list = healthy). ``require`` entries are revision ids or number prefixes (``"0025"``) that must be in the chain."""
    revs = revisions(versions)
    found: list[str] = []
    if not revs:
        return ["no migration files"]
    for rev, (downs, fname) in revs.items():
        if not fname.startswith(rev):
            found.append(f"{fname}: file name does not start with its revision id {rev}")
        if len(downs) > 1:
            found.append(f"{rev}: merge revision (down_revision {downs}); the history must be linear")
        for d in downs:
            if d not in revs:
                found.append(f"{rev}: down_revision {d!r} does not resolve to any revision")
    downs_all = {d for downs, _ in revs.values() for d in downs}
    heads = sorted(r for r in revs if r not in downs_all)
    bases = sorted(r for r, (downs, _) in revs.items() if not downs)
    if len(heads) != 1:
        found.append(f"expected exactly one head, found {len(heads)}: {heads}")
    if len(bases) != 1:
        found.append(f"expected exactly one base, found {len(bases)}: {bases}")
    # linear walk from the base: every revision must be reached exactly once
    children: dict[str, list[str]] = {}
    for r, (downs, _) in revs.items():
        for d in downs:
            children.setdefault(d, []).append(r)
    if any(len(v) > 1 for v in children.values()):
        found.append("a revision has more than one child (branch): " + str(sorted(k for k, v in children.items() if len(v) > 1)))
    elif len(bases) == 1:
        walk, cur = [bases[0]], bases[0]
        while cur in children and len(walk) <= len(revs):
            cur = children[cur][0]
            walk.append(cur)
        if len(walk) != len(revs) or len(set(walk)) != len(walk):
            found.append(f"chain from the base reaches {len(set(walk))} of {len(revs)} revisions")
    try:
        nums = sorted(number(r) for r in revs)
    except ValueError:
        found.append("a revision id does not start with its number")
        nums = []
    if nums and nums != list(range(1, nums[-1] + 1)):
        found.append(f"revision numbers are not contiguous from 0001: {nums}")
    for need in require:
        if not any(r == need or r.startswith(need if "_" in need else need + "_") for r in revs):
            found.append(f"required historical revision {need!r} is not in the chain")
    return found


def assert_chain(versions: Path | None = None, require: tuple[str, ...] = ()) -> str:
    """Raise unless the history is healthy and contains every ``require`` entry; return the head revision id."""
    found = problems(versions, require)
    if found:
        raise MigrationChainError("; ".join(found))
    return repository_head(versions)


def repository_heads(versions: Path | None = None) -> list[str]:
    revs = revisions(versions)
    downs = {d for ds, _ in revs.values() for d in ds}
    return sorted(r for r in revs if r not in downs)


def repository_head(versions: Path | None = None) -> str:
    """The single head of the (structurally valid) chain; raises MigrationChainError otherwise."""
    found = problems(versions)
    if found:
        raise MigrationChainError("; ".join(found))
    return repository_heads(versions)[0]


def chain(versions: Path | None = None) -> list[str]:
    """Revision ids from the base to the head (validates the chain first)."""
    head = repository_head(versions)
    revs = revisions(versions)
    out = [head]
    while revs[out[-1]][0]:
        out.append(revs[out[-1]][0][0])
    return out[::-1]


def head_number(versions: Path | None = None) -> int:
    return number(repository_head(versions))


def chain_ok(versions: Path | None = None, require: tuple[str, ...] = (), min_head: int = 1) -> tuple[bool, str]:
    """(ok, detail) for the evaluators: healthy chain, required revisions present, head number >= ``min_head``."""
    try:
        found = problems(versions, require)
    except MigrationChainError as exc:
        return False, str(exc)
    if found:
        return False, "; ".join(found)
    head = repository_head(versions)
    if number(head) < min_head:
        return False, f"head {head} is older than the registered baseline {min_head:04d}"
    return True, head
