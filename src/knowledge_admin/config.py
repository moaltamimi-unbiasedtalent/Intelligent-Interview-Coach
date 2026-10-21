"""ONE authoritative runtime configuration for the knowledge runtime (package 02A, REQ-OWN-05 K1/K2).

The API process and the job worker must use the SAME database, the SAME data root, the SAME private-file directory and the SAME collection
ids; before this module each of them derived those values on its own (the private-file directory silently defaulted to the system
temporary directory, so uploaded sources vanished with the container). There is NO second source of truth here: every value is derived
from the existing sources (the application config's ``database_url``, ``src.copilot.constants`` data root, the copilot config's Chroma
directory, the existing ``KNOWLEDGE_STORAGE_DIR`` override and ``API_ENV``) and this object only gathers them in one place so that both
processes (and the identity guard) read the same thing.

SECRET HYGIENE: ``database_url`` can carry a password. It is excluded from ``repr`` and from every ``to_safe_dict``; only the 02K
``DatabaseIdentity`` (kind + SHA-256 fingerprint of the credential-free URL) and ``DataRootIdentity`` (label + short hash) ever leave
the process. No absolute path is ever returned by ``to_safe_dict``.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from src import constants as app_constants
from src.copilot import constants
from src.knowledge_admin import policy as P
from src.knowledge_admin.contracts import DataRootIdentity, DatabaseIdentity, data_root_identity, database_fingerprint

HOSTED_ENVIRONMENTS = frozenset({"staging", "production"})
_DEV_ALIASES = frozenset({"development", "dev", "local", "test", "testing", ""})
PRIVATE_FILES_SUBDIR = "knowledge_private"       # under the data root: it rides on the same persistent volume as the indexes


def normalise_environment(raw: str | None) -> str:
    """``development`` | ``staging`` | ``production`` | ``unknown`` (an unrecognised name is treated as hosted-strict by ``is_hosted``)."""
    value = (raw or "").strip().lower()
    if value in _DEV_ALIASES:
        return "development"
    if value in HOSTED_ENVIRONMENTS:
        return value
    return "unknown"


def _is_under(path: str, parent: str) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class KnowledgeRuntimeConfig:
    database_url: str = field(repr=False)            # may contain credentials: NEVER serialised
    data_root: str = field(repr=False)               # absolute path: never serialised, only its short hash
    chroma_dir: str = field(repr=False)
    private_files_dir: str = field(repr=False)
    governed_collection: str = P.COLLECTION
    curated_collection: str = constants.CHROMA_COLLECTION_NAME
    environment: str = "development"
    private_files_explicit: bool = False             # True when KNOWLEDGE_STORAGE_DIR was set by the operator

    @property
    def hosted(self) -> bool:
        """Staging, production and any unrecognised environment name fail closed."""
        return self.environment != "development"

    @property
    def collection_ids(self) -> tuple[str, ...]:
        return (self.curated_collection, self.governed_collection)

    def database_identity(self) -> DatabaseIdentity:
        return database_fingerprint(self.database_url)

    def data_root_identity(self) -> DataRootIdentity:
        return data_root_identity(self.data_root)

    def placement_problems(self) -> list[str]:
        """Safe codes for a configuration that would lose data. Hosted only (development keeps working with a labelled warning)."""
        problems: list[str] = []
        tmp = tempfile.gettempdir()
        if self.private_files_explicit and _is_under(self.private_files_dir, tmp):
            problems.append("private_files_in_temp_directory")
        if _is_under(self.chroma_dir, tmp):
            problems.append("index_in_temp_directory")
        if _is_under(self.data_root, tmp):
            problems.append("data_root_in_temp_directory")
        db = self.database_identity()
        if db.kind == "sqlite":
            problems.append("database_is_sqlite")
        return problems

    def to_safe_dict(self) -> dict:
        """Identity-grade facts only: kinds, fingerprints, labels, collection ids. No URL, no path."""
        return {"environment": self.environment, "hosted": self.hosted, "database": self.database_identity().to_dict(),
                "data_root": self.data_root_identity().to_dict(),
                "private_files": {"label": "knowledge-private-files", "explicit": self.private_files_explicit,
                                  "inside_data_root": _is_under(self.private_files_dir, self.data_root)},
                "collections": list(self.collection_ids)}


def _bind_url(session_factory: Any) -> str | None:
    try:
        bind = session_factory.kw.get("bind")
        return bind.url.render_as_string(hide_password=False) if bind is not None else None
    except Exception:  # noqa: BLE001
        return None


def resolve_knowledge_runtime_config(app_config: Any = None, copilot_config: Any = None, *, session_factory: Any = None,
                                     env: Mapping[str, str] | None = None) -> KnowledgeRuntimeConfig:
    """Derive the runtime config from the EXISTING sources. The connected engine (when given) wins over the config value, because the
    engine is what the process actually talks to; the data root comes from ``constants.data_path`` at call time so that
    ``COPILOT_DATA_DIR`` is honoured identically by the API and the worker."""
    e = env if env is not None else os.environ
    root = str(constants.resolve_data_root())
    chroma = getattr(copilot_config, "chroma_persist_dir", None) or os.path.join(root, "chroma")
    explicit = (e.get("KNOWLEDGE_STORAGE_DIR") or "").strip()
    return KnowledgeRuntimeConfig(
        database_url=_bind_url(session_factory) or getattr(app_config, "database_url", None) or app_constants.DEFAULT_DATABASE_URL,
        data_root=root, chroma_dir=str(chroma), private_files_dir=explicit or os.path.join(root, PRIVATE_FILES_SUBDIR),
        governed_collection=P.COLLECTION, curated_collection=constants.CHROMA_COLLECTION_NAME,
        environment=normalise_environment(e.get("API_ENV", "development")), private_files_explicit=bool(explicit))
