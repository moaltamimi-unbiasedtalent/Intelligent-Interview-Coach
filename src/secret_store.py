"""SecretStore abstraction (P10B-W10.6, W10.0 decision AD-04).

Secret VALUES are never retrievable through the Admin surface. The interface deliberately has NO method that
returns a value to an administrator:

* ``is_configured(name)`` and ``source(name)`` answer metadata questions only (no prefix, suffix or mask);
* ``supports_write`` says whether the adapter can replace a value at all;
* ``set(name, value)`` exists only for adapters that support it; read-only adapters raise ``SecretStoreReadOnly``;
* ``get_for_runtime(name)`` is for APPLICATION code that must call a provider. It is the only read path, it
  returns a ``SecretStr`` (masked if printed or logged), and no Admin route, schema or audit payload may call it
  (``scripts/eval_admin_integrations.py`` enforces this).

The only production adapter is environment-backed (including the optional Streamlit secrets file the runtime
already reads): externally managed and read-only. Ask4Mo never claims to rotate an environment variable, never
writes ``.env`` and never mutates the process environment. No secure writable store exists in this architecture,
so none is invented: ``InMemorySecretStore`` is a clearly labelled TEST adapter that is never wired in production.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import SecretStr

from src.core import secrets as _runtime


class SecretStoreReadOnly(RuntimeError):
    """The active store cannot write: the credential is managed outside Ask4Mo."""


class SecretStore(Protocol):
    name: str
    supports_write: bool

    def is_configured(self, secret_name: str) -> bool: ...

    def source(self, secret_name: str) -> str: ...

    def get_for_runtime(self, secret_name: str) -> SecretStr | None: ...

    def set(self, secret_name: str, value: str) -> None: ...


class EnvironmentSecretStore:
    """Externally managed, read-only. Reads exactly what the runtime reads (secrets file, then environment)."""

    name = "environment"
    supports_write = False

    def is_configured(self, secret_name: str) -> bool:
        return bool(_runtime.read_setting(secret_name))

    def source(self, secret_name: str) -> str:
        if _runtime.read_streamlit(secret_name):
            return "secrets_file"
        return "environment" if _runtime.read_env(secret_name) else "none"

    def get_for_runtime(self, secret_name: str) -> SecretStr | None:
        return _runtime.read_secret(secret_name)

    def set(self, secret_name: str, value: str) -> None:
        raise SecretStoreReadOnly("This credential is managed outside Ask4Mo and cannot be changed here.")


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

    def set(self, secret_name: str, value: str) -> None:
        self._values[secret_name] = value


_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _store
    if _store is None:
        _store = EnvironmentSecretStore()
    return _store
