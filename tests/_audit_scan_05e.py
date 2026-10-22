"""Static scan (05E): every audit/incident context KEY the source can emit, found without running the code.

The runtime listener (``src/audit_allowlist.py``) rejects an unlisted key in strict mode only when the code path executes. This scan covers the paths no test happens to
execute: it reads every module under ``src`` and ``scripts`` and collects the literal keys passed as audit context through the known writers. A key that is built
dynamically (``context=changed``) cannot be seen here and is covered by the runtime listener.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Formal parameters of ``build_audit`` that are NOT context keys.
_BUILD_AUDIT_PARAMS = {"event_type", "actor_user_id", "request_id", "target_type", "target_id", "result"}
# Writers that take the audit spec first and add the remaining keyword arguments to its context (extra safe fields).
_STAGE_FUNCS = {"_stage", "_stage_audit"}


def _fname(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _dict_keys(node: ast.AST) -> set[str]:
    out: set[str] = set()
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out.add(k.value)
            if isinstance(v, ast.Dict):
                out |= _dict_keys(v)
    return out


def emitted_keys(paths=None) -> dict[str, set[str]]:
    """{"audit": {keys}, "incident": {keys}} found in the source, with the files they came from available through ``emitted_key_sources``."""
    found = {"audit": set(), "incident": set()}
    for key, where in emitted_key_sources(paths):
        found[where[0]].add(key)
    return found


def emitted_key_sources(paths=None) -> list[tuple[str, tuple[str, str]]]:
    roots = paths or [ROOT / "src", ROOT / "scripts"]
    out: list[tuple[str, tuple[str, str]]] = []
    for base in roots:
        for path in sorted(Path(base).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = str(path.relative_to(ROOT))
            for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
                name = _fname(call)
                if name == "build_audit":
                    for kw in call.keywords:
                        if kw.arg and kw.arg not in _BUILD_AUDIT_PARAMS:
                            out.append((kw.arg, ("audit", rel)))
                        elif kw.arg is None:
                            continue                                       # **context: dynamic, covered at runtime
                if name in _STAGE_FUNCS and len(call.args) >= 2:
                    for kw in call.keywords:
                        if kw.arg:
                            out.append((kw.arg, ("audit", rel)))
                for kw in call.keywords:
                    if kw.arg == "context" and name in ("record", "AuditEvent", "_event_row"):
                        for k in _dict_keys(kw.value):
                            out.append((k, ("audit", rel)))
                    if kw.arg == "meta" and name in ("_event", "AdminIncidentEvent"):
                        for k in _dict_keys(kw.value):
                            out.append((k, ("incident", rel)))
                if name == "_event":                                        # incidents: _event(s, inc, action=..., meta={...})
                    for kw in call.keywords:
                        if kw.arg == "meta":
                            for k in _dict_keys(kw.value):
                                out.append((k, ("incident", rel)))
    return out
