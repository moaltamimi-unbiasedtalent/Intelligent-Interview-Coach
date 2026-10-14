"""SecretStore abstraction (P10B-W10.6, W10.0 decision AD-04; writable encrypted adapter added in W12.4B).

Secret VALUES are never retrievable through the Admin surface. The interface deliberately has NO method that
returns a value to an administrator:

* ``is_configured(name)`` and ``source(name)`` answer metadata questions only (no prefix, suffix, mask or fingerprint);
* ``supports_write`` says whether the adapter can replace a value at all;
* ``set(name, value, ...)`` / ``remove(name, ...)`` exist only for adapters that support them; read-only adapters raise
  ``SecretStoreReadOnly``;
* ``get_for_runtime(name)`` is for APPLICATION code that must call a provider. It is the only read path, it
  returns a ``SecretStr`` (masked if printed or logged), and no Admin route, schema or audit payload may call it
  (``scripts/eval_admin_integrations.py`` enforces this).

Adapters:

* ``EnvironmentSecretStore``: externally managed and read-only (the FALLBACK layer). Ask4Mo never rotates an
  environment variable, never writes ``.env`` and never mutates the process environment.
* ``EncryptedDatabaseSecretStore`` (W12.4B): a writable store that keeps each credential ONLY as AES-256-GCM
  ciphertext (``cryptography`` AESGCM, no custom cryptography) in ``managed_secrets``. The 32-byte master key is
  deployment bootstrap configuration (``SECRET_STORE_MASTER_KEY``, base64): it cannot live in the database it
  encrypts and has no Admin control. Ciphertext is bound to its (integration, slot) as associated data.
* ``LayeredSecretStore`` (the production store when ``SECRET_STORE_BACKEND=encrypted_database``): managed value
  first, environment fallback second, otherwise not configured. Environment secrets are never copied in.
* ``InMemorySecretStore``: a clearly labelled TEST adapter that is never wired in production.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import threading
import time
from typing import Any, Protocol

from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from src.core import secrets as _runtime

BACKEND_ENV = "SECRET_STORE_BACKEND"
MASTER_KEY_ENV = "SECRET_STORE_MASTER_KEY"
BACKEND_ENVIRONMENT = "environment"
BACKEND_ENCRYPTED = "encrypted_database"
CACHE_TTL_SECONDS = 5.0     # cross-process convergence bound for a rotation, like the AI configuration cache


class SecretStoreError(RuntimeError):
    """Base class. Messages are fixed, user-safe copy: never a value, key material or exception text."""


class SecretStoreReadOnly(SecretStoreError):
    """The active store cannot write: the credential is managed outside Ask4Mo."""


class SecretStoreUnavailable(SecretStoreError):
    """The secure writable store cannot be used right now. ``reason`` is one of the bounded codes below."""

    def __init__(self, reason: str) -> None:
        super().__init__("The secure credential store is unavailable.")
        self.reason = reason


class SecretStoreStale(SecretStoreError):
    """The credential changed since the caller last read its revision."""


class SecretSlotUnknown(SecretStoreError):
    """No code-defined (integration, slot) exists for this name."""


UNAVAILABLE_REASONS = ("key_missing", "key_malformed", "store_error", "not_bound")


class MasterKeyInvalid(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_master_key(raw: str | None) -> bytes:
    """Strict: standard base64 of EXACTLY 32 bytes. No password derivation, no padding repair, no truncation."""
    if raw is None or not raw.strip():
        raise MasterKeyInvalid("key_missing")
    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise MasterKeyInvalid("key_malformed") from None
    if len(key) != 32:
        raise MasterKeyInvalid("key_malformed")
    return key


def master_key_state(raw: str | None = None) -> str | None:
    """None when the key is usable, else the bounded reason. Never returns key material."""
    try:
        parse_master_key(raw if raw is not None else os.environ.get(MASTER_KEY_ENV))
    except MasterKeyInvalid as exc:
        return exc.reason
    return None


def _key_id(key: bytes) -> str:
    return hashlib.blake2b(b"ask4mo.secret_store.key_id.v1" + key, digest_size=4).hexdigest()


def _aad(code: str, slot: str) -> bytes:
    return f"ask4mo.managed_secret.v1:{code}:{slot}".encode()


class SecretStore(Protocol):
    name: str
    supports_write: bool

    def is_configured(self, secret_name: str) -> bool: ...

    def source(self, secret_name: str) -> str: ...

    def get_for_runtime(self, secret_name: str) -> SecretStr | None: ...

    def set(self, secret_name: str, value: str, **kw: Any) -> None: ...


class EnvironmentSecretStore:
    """Externally managed, read-only. Reads exactly the deployment layer (secrets file, then environment)."""

    name = "environment"
    supports_write = False

    def is_configured(self, secret_name: str) -> bool:
        return bool(_runtime.read_environment_setting(secret_name))

    def source(self, secret_name: str) -> str:
        if _runtime.read_streamlit(secret_name):
            return "secrets_file"
        return "environment" if _runtime.read_env(secret_name) else "none"

    def get_for_runtime(self, secret_name: str) -> SecretStr | None:
        raw = _runtime.read_environment_setting(secret_name)
        return SecretStr(raw) if raw else None

    def set(self, secret_name: str, value: str, **kw: Any) -> None:
        raise SecretStoreReadOnly("This credential is managed outside Ask4Mo and cannot be changed here.")

    def remove(self, secret_name: str, **kw: Any) -> None:
        raise SecretStoreReadOnly("This credential is managed outside Ask4Mo and cannot be changed here.")

    def write_state(self) -> dict:
        return {"state": "read_only", "reason": None}

    def managed_meta(self, secret_name: str) -> dict | None:
        return None


def _locate(secret_name: str):
    """(integration code, slot) for a credential NAME. Only code-defined slots exist; raises SecretSlotUnknown."""
    from src.integrations import REGISTRY   # lazy: integrations imports this module

    for d in REGISTRY.values():
        for c in d.credentials:
            if c.external_name == secret_name:
                return d.code, c.slot
    raise SecretSlotUnknown(secret_name)


def managed_secret_names() -> frozenset[str]:
    from src.integrations import REGISTRY

    return frozenset(c.external_name for d in REGISTRY.values() for c in d.credentials)


class EncryptedDatabaseSecretStore:
    """Writable adapter: AES-256-GCM ciphertext rows in ``managed_secrets``. Holds no plaintext, mask, fingerprint or history."""

    name = "encrypted_database"
    atomic_audit = True     # the audit event is staged in the same transaction as the change

    def __init__(self, session_factory: sessionmaker | None, master_key: str | None = None) -> None:
        self._sf = session_factory
        self._raw_key = master_key if master_key is not None else os.environ.get(MASTER_KEY_ENV)
        self._cache: dict[str, tuple[float, str | None]] = {}
        self._lock = threading.Lock()
        self.last_read_failure: dict[str, str] = {}

    # -- state ------------------------------------------------------------------------------------------------
    def _key(self) -> bytes:
        try:
            return parse_master_key(self._raw_key)
        except MasterKeyInvalid as exc:
            raise SecretStoreUnavailable(exc.reason) from None

    def write_state(self) -> dict:
        if self._sf is None:
            return {"state": "unavailable", "reason": "not_bound"}
        reason = master_key_state(self._raw_key)
        if reason:
            return {"state": "unavailable", "reason": reason}
        return {"state": "writable", "reason": None}

    @property
    def supports_write(self) -> bool:   # type: ignore[override]
        return self.write_state()["state"] == "writable"

    def invalidate(self) -> None:
        with self._lock:
            self._cache.clear()

    # -- reads ------------------------------------------------------------------------------------------------
    def _row(self, s, code: str, slot: str):
        from src.persistence import ManagedSecret

        return s.scalar(select(ManagedSecret).where(ManagedSecret.integration_code == code, ManagedSecret.slot == slot))

    def is_configured(self, secret_name: str) -> bool:
        return self.managed_meta(secret_name) is not None

    def source(self, secret_name: str) -> str:
        return "managed" if self.is_configured(secret_name) else "none"

    def managed_meta(self, secret_name: str) -> dict | None:
        """Metadata only: revision and timestamps. Never ciphertext, nonce or key information."""
        if self._sf is None:
            return None
        try:
            code, slot = _locate(secret_name)
            with self._sf() as s:
                row = self._row(s, code, slot)
                if row is None:
                    return None
                return {"revision": row.revision, "updated_at": row.updated_at, "readable": secret_name not in self.last_read_failure}
        except Exception:  # noqa: BLE001 - a store problem is reported as "no managed metadata", never raised into a page
            return None

    def get_for_runtime(self, secret_name: str) -> SecretStr | None:
        value = self._managed_value(secret_name)
        return SecretStr(value) if value else None

    def _managed_value(self, secret_name: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(secret_name)
            if hit and hit[0] > now:
                return hit[1]
        value = self._decrypt_from_db(secret_name)
        with self._lock:
            self._cache[secret_name] = (now + CACHE_TTL_SECONDS, value)
        return value

    def _decrypt_from_db(self, secret_name: str) -> str | None:
        if self._sf is None:
            return None
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            code, slot = _locate(secret_name)
            with self._sf() as s:
                row = self._row(s, code, slot)
                if row is None:
                    self.last_read_failure.pop(secret_name, None)
                    return None
                blob = (bytes(row.ciphertext), bytes(row.nonce))
            plain = AESGCM(self._key()).decrypt(blob[1], blob[0], _aad(code, slot)).decode("utf-8")
            self.last_read_failure.pop(secret_name, None)
            return plain
        except Exception:  # noqa: BLE001 - wrong key, tampering, missing key or store error: unreadable, never an exception text
            self.last_read_failure[secret_name] = "unreadable"
            return None

    # -- writes -----------------------------------------------------------------------------------------------
    def set(self, secret_name: str, value: str, *, actor_user_id: int | None = None, expected_revision: int | None = None,
            audit: dict | None = None, audit_extra: dict | None = None) -> dict:
        """Encrypt and upsert in ONE transaction together with the staged audit event: if the audit fails, nothing is stored."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        from src.admin_repository import _stage
        from src.persistence import ManagedSecret, utcnow

        if self._sf is None:
            raise SecretStoreUnavailable("not_bound")
        code, slot = _locate(secret_name)
        key = self._key()
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), _aad(code, slot))
        try:
            with self._sf() as s:
                row = self._row(s, code, slot)
                if expected_revision is not None and (row.revision if row else 0) != expected_revision:
                    raise SecretStoreStale("stale")
                action = "rotated" if row else "created"
                if row is None:
                    row = ManagedSecret(integration_code=code, slot=slot, revision=1, created_at=utcnow())
                    s.add(row)
                else:
                    row.revision += 1
                row.ciphertext, row.nonce, row.key_id = ciphertext, nonce, _key_id(key)
                row.updated_at, row.updated_by_user_id = utcnow(), actor_user_id
                _stage(s, audit, slot=slot, action=action, **(audit_extra or {}))
                s.commit()
                revision = row.revision
        except SecretStoreError:
            raise
        except Exception:  # noqa: BLE001
            raise SecretStoreUnavailable("store_error") from None
        self.invalidate()
        return {"action": action, "revision": revision}

    def remove(self, secret_name: str, *, actor_user_id: int | None = None, expected_revision: int | None = None,
               audit: dict | None = None) -> dict:
        from src.admin_repository import _stage

        if self._sf is None:
            raise SecretStoreUnavailable("not_bound")
        code, slot = _locate(secret_name)
        try:
            with self._sf() as s:
                row = self._row(s, code, slot)
                if row is None:
                    raise SecretStoreStale("absent")
                if expected_revision is not None and row.revision != expected_revision:
                    raise SecretStoreStale("stale")
                s.execute(delete(type(row)).where(type(row).id == row.id))
                _stage(s, audit, slot=slot, action="removed")
                s.commit()
        except SecretStoreError:
            raise
        except Exception:  # noqa: BLE001
            raise SecretStoreUnavailable("store_error") from None
        self.invalidate()
        return {"action": "removed"}


class LayeredSecretStore:
    """Managed encrypted credential first, environment fallback second, otherwise not configured (W12.4B)."""

    name = "managed_with_environment_fallback"
    atomic_audit = True

    def __init__(self, managed: EncryptedDatabaseSecretStore, environment: EnvironmentSecretStore | None = None) -> None:
        self.managed = managed
        self.environment = environment or EnvironmentSecretStore()

    @property
    def supports_write(self) -> bool:   # type: ignore[override]
        return self.managed.supports_write

    def write_state(self) -> dict:
        return self.managed.write_state()

    def managed_meta(self, secret_name: str) -> dict | None:
        return self.managed.managed_meta(secret_name)

    def is_configured(self, secret_name: str) -> bool:
        return self.managed.is_configured(secret_name) or self.environment.is_configured(secret_name)

    def source(self, secret_name: str) -> str:
        if self.managed.is_configured(secret_name):
            return "managed"
        return self.environment.source(secret_name)

    def get_for_runtime(self, secret_name: str) -> SecretStr | None:
        return self.managed.get_for_runtime(secret_name) or self.environment.get_for_runtime(secret_name)

    def set(self, secret_name: str, value: str, **kw: Any) -> dict:
        return self.managed.set(secret_name, value, **kw)

    def remove(self, secret_name: str, **kw: Any) -> dict:
        return self.managed.remove(secret_name, **kw)

    def managed_value(self, secret_name: str) -> str | None:
        """The resolver installed into ``src.core.secrets``: only code-defined credential names are ever answered."""
        if secret_name not in managed_secret_names():
            return None
        return self.managed._managed_value(secret_name)


class InMemorySecretStore:
    """TEST-ONLY writable adapter (never constructed by the application)."""

    name = "in_memory_test"
    supports_write = True

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._values = dict(initial or {})

    def is_configured(self, secret_name: str) -> bool:
        return bool(self._values.get(secret_name))

    def source(self, secret_name: str) -> str:
        return "in_memory_test" if self._values.get(secret_name) else "none"

    def get_for_runtime(self, secret_name: str) -> SecretStr | None:
        v = self._values.get(secret_name)
        return SecretStr(v) if v else None

    def set(self, secret_name: str, value: str, **kw: Any) -> None:
        self._values[secret_name] = value

    def remove(self, secret_name: str, **kw: Any) -> None:
        self._values.pop(secret_name, None)

    def write_state(self) -> dict:
        return {"state": "writable", "reason": None}

    def managed_meta(self, secret_name: str) -> dict | None:
        return None


# ------------------------------------------------------------------------------------------------------------
# Selection (deployment-owned): SECRET_STORE_BACKEND = environment (default) | encrypted_database
# ------------------------------------------------------------------------------------------------------------

_store: SecretStore | None = None
_session_factory: sessionmaker | None = None


def selected_backend() -> str:
    raw = (os.environ.get(BACKEND_ENV) or BACKEND_ENVIRONMENT).strip().lower()
    return raw if raw in (BACKEND_ENVIRONMENT, BACKEND_ENCRYPTED) else "invalid"


def bind_secret_store(session_factory: sessionmaker) -> SecretStore:
    """Bind the application database to the selected backend and (re)install the runtime resolver. Called at API and
    worker startup. With the default ``environment`` backend nothing changes: no resolver, no database access."""
    global _store, _session_factory
    if selected_backend() != BACKEND_ENCRYPTED:
        return get_secret_store()
    _session_factory = session_factory
    _store = None
    return get_secret_store()


def get_secret_store() -> SecretStore:
    global _store
    if _store is None:
        if selected_backend() == BACKEND_ENCRYPTED:
            layered = LayeredSecretStore(EncryptedDatabaseSecretStore(_session_factory))
            _runtime.set_managed_resolver(layered.managed_value)
            _store = layered
        else:
            _runtime.set_managed_resolver(None)
            _store = EnvironmentSecretStore()
    return _store


def reset_secret_store_for_tests() -> None:
    global _store, _session_factory
    _store = None
    _session_factory = None
    _runtime.set_managed_resolver(None)
