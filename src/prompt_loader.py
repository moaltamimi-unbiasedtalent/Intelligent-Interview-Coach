"""Versioned prompt asset format and loader contract (package 01B0, REVIEW-02 R1-R4).

This module is a CONTRACT only. No production prompt text lives in assets yet: package
01B migrates the literals in ``src/agent/policies.py``, ``src/prompts.py`` and
``src/copilot/rag/prompts.py``; package 06C adds per-language behaviour. Both conform to
the interface below, verified by ``tests/contracts/test_prompt_loader_01b0.py``.

Public interface (stable; extend, never change in place)
--------------------------------------------------------
* ``PromptAsset``      frozen model: ``id``, ``family``, ``version`` (semver string),
                       ``variables`` (declared names), ``compatible_with`` (consumer
                       contract ids), ``description``, ``status`` (``approved`` |
                       ``draft`` | ``deprecated``), ``deprecated_reason``,
                       ``rollback_to`` (version to fall back to), ``body``, ``recorded_sha256``
                       and the computed ``sha256`` (hash of the UTF-8 body).
* ``PromptLoader``     runtime-checkable Protocol: ``families()``, ``versions(family)``,
                       ``get(family, version)``, ``resolve(family, version=None)``,
                       ``render(asset, variables)``, ``declared_versions_with_hash()``.
* ``FilePromptLoader`` loads a directory tree (see below). Read-only, offline, no provider
                       or network use.
* Errors (all subclass ``PromptError``): ``MissingPromptVersion``, ``InvalidPromptAsset``
  (also integrity-hash mismatch), ``VariableMismatch``, ``IncompatiblePrompt``
  (raised by ``PromptAsset.check_compatible(consumer_id)``).

Declared version vs hash
------------------------
``version`` is a human-declared semantic version, independent of content. ``sha256`` is an
integrity check only: when an asset records ``sha256`` in its front matter (or the
``current.json`` pointer records one) a mismatch refuses the load. Hash and version are
never derived from one another. ``declared_versions_with_hash()`` returns
``{family: {"version": ..., "sha256": ...}}`` for the resolved current version of each
family, intended for a later ``production_versions()`` extension (NOT wired by 01B0).

On-disk layout (the example in REVIEW-02 is an example; this format is a superset)
-------------------------------------------------------------------------------
``<root>/<family path>/<name>.v<semver>.md`` e.g. ``agent/system.v3.0.0.md``, plus an
optional ``<root>/current.json`` pointer ``{"<family>": "<version>"}`` or
``{"<family>": {"version": "...", "sha256": "..."}}``. Family ids are ``<dir>/<name>``
(``agent/system``). Without a pointer, the highest APPROVED semver is current. Rollback to
an earlier approved version is a pointer edit, no code change. ``README.md`` files are
ignored.

File format: ``---`` front matter lines ``key: value`` ``---`` then the body. Lists are
written ``[a, b]``. Keys: id, family, version, variables, compatible_with, description,
status, deprecated_reason, rollback_to, sha256. The body is everything after the closing
``---`` line, byte for byte (the hash input). Placeholders are ``{name}`` (literal braces
are ``{{`` and ``}}``); only plain identifiers are allowed (no format specs, attribute or
index access) and the set used must equal the declared ``variables``. Rendering equals
``str.format`` for such bodies, so migrated prompts can stay byte-identical.

Admin free-text editing of system instructions is out of scope by design: assets are
code-reviewed files; the loader exposes no write path.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "PromptError", "MissingPromptVersion", "InvalidPromptAsset", "VariableMismatch",
    "IncompatiblePrompt", "PromptAsset", "PromptLoader", "FilePromptLoader",
    "parse_semver", "compute_sha256", "parse_asset", "STATUSES",
]

STATUSES = ("approved", "draft", "deprecated")
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FAMILY = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)+$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_KEYS = {"id", "family", "version", "variables", "compatible_with", "description", "status",
         "deprecated_reason", "rollback_to", "sha256"}
_FILE = re.compile(r"^(?P<name>[a-z0-9_]+)\.v(?P<ver>\d+\.\d+\.\d+)\.md$")


class PromptError(Exception):
    """Base class of every prompt contract error."""


class MissingPromptVersion(PromptError):
    """The family or the requested version does not exist (or the pointer targets none)."""


class InvalidPromptAsset(PromptError):
    """Malformed front matter/schema, a body placeholder problem, or an integrity mismatch."""


class VariableMismatch(PromptError):
    """Render-time variables are missing or unknown versus the declared set."""


class IncompatiblePrompt(PromptError):
    """The asset does not declare compatibility with the requesting consumer contract."""


def parse_semver(version: str) -> tuple[int, int, int]:
    match = _SEMVER.match(version) if isinstance(version, str) else None
    if not match:
        raise InvalidPromptAsset(f"not a semantic version (MAJOR.MINOR.PATCH): {version!r}")
    return int(match[1]), int(match[2]), int(match[3])


def compute_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _placeholders(body: str) -> set[str]:
    names: set[str] = set()
    try:
        parsed = list(string.Formatter().parse(body))
    except ValueError as exc:
        raise InvalidPromptAsset(f"invalid template braces: {exc}") from exc
    for _lit, field, spec, conv in parsed:
        if field is None:
            continue
        if not _IDENT.match(field) or spec or conv:
            raise InvalidPromptAsset(f"unsupported placeholder {{{field}}} (plain names only)")
        names.add(field)
    return names


@dataclass(frozen=True)
class PromptAsset:
    id: str
    family: str
    version: str
    variables: tuple[str, ...]
    compatible_with: tuple[str, ...]
    description: str
    status: str
    body: str
    deprecated_reason: str = ""
    rollback_to: str = ""
    recorded_sha256: str = ""

    @property
    def sha256(self) -> str:
        return compute_sha256(self.body)

    @property
    def semver(self) -> tuple[int, int, int]:
        return parse_semver(self.version)

    def check_compatible(self, consumer: str) -> None:
        if consumer not in self.compatible_with:
            raise IncompatiblePrompt(
                f"{self.family}@{self.version} is not compatible with consumer {consumer!r}"
                f" (declares {list(self.compatible_with)})")


def _list(value: str, key: str) -> tuple[str, ...]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise InvalidPromptAsset(f"{key} must be a list written [a, b]")
    items = tuple(p.strip() for p in value[1:-1].split(",") if p.strip())
    if len(set(items)) != len(items):
        raise InvalidPromptAsset(f"{key} contains duplicates")
    return items


def parse_asset(text: str, *, source: str = "<memory>") -> PromptAsset:
    """Parse and validate one asset file's text. Raises ``InvalidPromptAsset``."""
    lines = text.split("\n")
    if lines[0].strip() != "---":
        raise InvalidPromptAsset(f"{source}: missing front matter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise InvalidPromptAsset(f"{source}: unterminated front matter") from None
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or key not in _KEYS:
            raise InvalidPromptAsset(f"{source}: unknown or malformed front matter line {line!r}")
        if key in meta:
            raise InvalidPromptAsset(f"{source}: duplicate key {key}")
        meta[key] = value.strip()
    body = "\n".join(lines[end + 1:])
    for req in ("id", "family", "version", "variables", "compatible_with", "description"):
        if not meta.get(req):
            raise InvalidPromptAsset(f"{source}: missing required field {req}")
    if not _FAMILY.match(meta["family"]):
        raise InvalidPromptAsset(f"{source}: invalid family id {meta['family']!r}")
    parse_semver(meta["version"])
    status = meta.get("status", "approved")
    if status not in STATUSES:
        raise InvalidPromptAsset(f"{source}: status must be one of {STATUSES}")
    variables = _list(meta["variables"], "variables")
    for name in variables:
        if not _IDENT.match(name):
            raise InvalidPromptAsset(f"{source}: invalid variable name {name!r}")
    compat = _list(meta["compatible_with"], "compatible_with")
    if not compat:
        raise InvalidPromptAsset(f"{source}: compatible_with must name a consumer contract")
    if status == "deprecated" and not meta.get("deprecated_reason"):
        raise InvalidPromptAsset(f"{source}: deprecated asset needs deprecated_reason")
    if meta.get("rollback_to"):
        parse_semver(meta["rollback_to"])
    if meta.get("sha256") and not _SHA.match(meta["sha256"]):
        raise InvalidPromptAsset(f"{source}: sha256 must be 64 lowercase hex characters")
    used = _placeholders(body)
    declared = set(variables)
    if used != declared:
        raise InvalidPromptAsset(
            f"{source}: body placeholders {sorted(used)} differ from declared variables "
            f"{sorted(declared)} (undeclared: {sorted(used - declared)}, "
            f"unused: {sorted(declared - used)})")
    asset = PromptAsset(
        id=meta["id"], family=meta["family"], version=meta["version"], variables=variables,
        compatible_with=compat, description=meta["description"], status=status, body=body,
        deprecated_reason=meta.get("deprecated_reason", ""),
        rollback_to=meta.get("rollback_to", ""), recorded_sha256=meta.get("sha256", ""))
    if asset.recorded_sha256 and asset.recorded_sha256 != asset.sha256:
        raise InvalidPromptAsset(
            f"{source}: integrity hash mismatch (recorded {asset.recorded_sha256[:12]}, "
            f"computed {asset.sha256[:12]})")
    return asset


@runtime_checkable
class PromptLoader(Protocol):
    def families(self) -> list[str]: ...
    def versions(self, family: str) -> list[str]: ...
    def get(self, family: str, version: str) -> PromptAsset: ...
    def resolve(self, family: str, version: str | None = None) -> PromptAsset: ...
    def render(self, asset: PromptAsset, variables: Mapping[str, object]) -> str: ...
    def declared_versions_with_hash(self) -> dict[str, dict[str, str]]: ...


class FilePromptLoader:
    """Loads and validates every asset under ``root`` eagerly (fail closed at load)."""

    def __init__(self, root: str | Path, *, pointer_file: str = "current.json") -> None:
        self._root = Path(root)
        if not self._root.is_dir():
            raise MissingPromptVersion(f"prompt asset root not found: {self._root}")
        self._assets: dict[str, dict[str, PromptAsset]] = {}
        for path in sorted(self._root.rglob("*.md")):
            rel = path.relative_to(self._root)
            if path.name.lower() == "readme.md":
                continue
            m = _FILE.match(path.name)
            if not m:
                raise InvalidPromptAsset(f"{rel}: file name must be <name>.v<semver>.md")
            asset = parse_asset(path.read_text(encoding="utf-8"), source=rel.as_posix())
            expected_family = "/".join((*rel.parent.parts, m["name"]))
            if asset.family != expected_family or asset.version != m["ver"]:
                raise InvalidPromptAsset(
                    f"{rel}: path implies {expected_family}@{m['ver']} but front matter "
                    f"declares {asset.family}@{asset.version}")
            by_ver = self._assets.setdefault(asset.family, {})
            if asset.version in by_ver:
                raise InvalidPromptAsset(f"{rel}: duplicate version")
            by_ver[asset.version] = asset
        self._pointers = self._load_pointers(self._root / pointer_file)

    def _load_pointers(self, path: Path) -> dict[str, tuple[str, str]]:
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise InvalidPromptAsset(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise InvalidPromptAsset(f"{path.name}: must be an object")
        out: dict[str, tuple[str, str]] = {}
        for family, entry in raw.items():
            if isinstance(entry, str):
                version, sha = entry, ""
            elif isinstance(entry, dict):
                version, sha = entry.get("version", ""), entry.get("sha256", "")
            else:
                version, sha = "", ""
            if not isinstance(version, str) or not isinstance(sha, str) or not version:
                raise InvalidPromptAsset(f"{path.name}: bad pointer for {family}")
            parse_semver(version)
            if family not in self._assets:
                raise MissingPromptVersion(f"pointer names unknown family {family}")
            out[family] = (version, sha)
        return out

    def families(self) -> list[str]:
        return sorted(self._assets)

    def versions(self, family: str) -> list[str]:
        if family not in self._assets:
            raise MissingPromptVersion(f"unknown prompt family {family!r}")
        return sorted(self._assets[family], key=parse_semver)

    def get(self, family: str, version: str) -> PromptAsset:
        parse_semver(version)
        try:
            return self._assets[family][version]
        except KeyError:
            raise MissingPromptVersion(f"{family}@{version} does not exist") from None

    def resolve(self, family: str, version: str | None = None) -> PromptAsset:
        """Return the requested version, else the pointer target, else highest approved.

        An explicit or pointed version must exist and must not be ``draft``; a pointer
        recording ``sha256`` must match the asset's computed hash.
        """
        if version is not None:
            asset = self.get(family, version)
        elif family in self._pointers:
            ver, sha = self._pointers[family]
            asset = self.get(family, ver)
            if sha and sha != asset.sha256:
                raise InvalidPromptAsset(f"pointer integrity mismatch for {family}@{ver}")
        else:
            approved = [v for v in self.versions(family)
                        if self._assets[family][v].status == "approved"]
            if not approved:
                raise MissingPromptVersion(f"{family} has no approved version")
            asset = self._assets[family][approved[-1]]
        if asset.status == "draft":
            raise MissingPromptVersion(f"{family}@{asset.version} is a draft, not approved")
        return asset

    def render(self, asset: PromptAsset, variables: Mapping[str, object]) -> str:
        given, declared = set(variables), set(asset.variables)
        missing, unknown = declared - given, given - declared
        if missing or unknown:
            raise VariableMismatch(
                f"{asset.family}@{asset.version}: missing {sorted(missing)}, "
                f"unknown {sorted(unknown)}")
        return asset.body.format_map({k: str(v) for k, v in variables.items()})

    def declared_versions_with_hash(self) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for family in self.families():
            asset = self.resolve(family)
            out[family] = {"version": asset.version, "sha256": asset.sha256}
        return out
