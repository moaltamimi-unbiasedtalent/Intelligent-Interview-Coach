"""Route-permission invariant for the admin surface (P10B-W10.1).

Discovers every router in ``src.api.routes`` and inspects each route's dependency graph for a
``require_permission(...)`` dependency (it exposes ``.permission``). Dependency introspection is used rather
than a source regex so a router-level dependency, a per-route dependency or a nested dependency all count,
and a route cannot silently lose its gate. Used by the tests and ``scripts/eval_admin_foundation.py``.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.routing import APIRoute

# Prefixes that make a route "admin/internal" and therefore permission-gated.
ADMIN_PREFIXES = ("/admin", "/reviewer", "/evaluation")
# Individual admin/internal routes that live in a candidate-facing router.
ADMIN_EXTRA_PATHS = ("/knowledge/diagnostics", "/auth/admin/audit")


@dataclass(frozen=True)
class AdminRoute:
    path: str            # path relative to the API prefix, e.g. "/admin/home"
    methods: tuple[str, ...]
    permissions: frozenset[str]
    route: APIRoute


def _permissions(route: APIRoute) -> frozenset[str]:
    found: set[str] = set()

    def walk(dep) -> None:
        perm = getattr(dep.call, "permission", None)
        if perm:
            found.add(perm)
        for sub in dep.dependencies:
            walk(sub)

    walk(route.dependant)
    return frozenset(found)


def _routers() -> list[APIRouter]:
    import src.api.routes as pkg

    out: list[APIRouter] = []
    for mod in pkgutil.iter_modules(pkg.__path__):
        m = importlib.import_module(f"{pkg.__name__}.{mod.name}")
        for value in vars(m).values():
            if isinstance(value, APIRouter) and value not in out:
                out.append(value)
    return out


def is_admin_path(path: str) -> bool:
    return path.startswith(ADMIN_PREFIXES) or path in ADMIN_EXTRA_PATHS


def admin_routes() -> list[AdminRoute]:
    found: dict[tuple[str, tuple[str, ...]], AdminRoute] = {}
    for router in _routers():
        for r in router.routes:
            if isinstance(r, APIRoute) and is_admin_path(r.path):
                methods = tuple(sorted(r.methods - {"HEAD", "OPTIONS"}))
                found[(r.path, methods)] = AdminRoute(r.path, methods, _permissions(r), r)
    return sorted(found.values(), key=lambda a: (a.path, a.methods))


def ungated(routes: list[AdminRoute] | None = None) -> list[AdminRoute]:
    return [r for r in (routes if routes is not None else admin_routes()) if not r.permissions]
