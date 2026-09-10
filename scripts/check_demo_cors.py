#!/usr/bin/env python
"""Ask4Mo demo CORS / frontend-origin readiness (DEV / DEMO ONLY).

Golden Demo Live Rehearsal #2 lost time because the frontend was started on a
non-default port, so the backend's CORS allow-list (which defaults to the canonical
demo origin http://localhost:3000) rejected the browser's preflight and the first
"Ask Mo" failed with a connection error. This check makes that failure explicit and
fast to diagnose BEFORE the live demo, instead of surfacing as a mystery in the UI.

It sends a real CORS preflight (OPTIONS + Origin + Access-Control-Request-Method) to
a backend endpoint and verifies the backend returns an Access-Control-Allow-Origin
that permits the demo frontend origin. Standard library only — no new dependency and
no new subsystem.

Canonical demo configuration (see docs/sprint4_demo_script.md):
    backend           http://localhost:8000
    frontend          http://localhost:3000
    FRONTEND_ORIGINS  http://localhost:3000

Override for a non-default demo host/port:
    BACKEND_URL=http://localhost:8000 FRONTEND_ORIGIN=http://localhost:3000 \
        python scripts/check_demo_cors.py

Exit code 0 when the origin is allowed; non-zero otherwise (with the exact fix).
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

BACKEND_URL = (os.environ.get("BACKEND_URL") or "http://localhost:8000").rstrip("/")
FRONTEND_ORIGIN = (os.environ.get("FRONTEND_ORIGIN") or "http://localhost:3000").rstrip("/")
_PROBE_PATH = "/api/v1/capabilities"  # a real CORS-guarded GET endpoint


def main() -> int:
    url = f"{BACKEND_URL}{_PROBE_PATH}"
    req = urllib.request.Request(url, method="OPTIONS")
    req.add_header("Origin", FRONTEND_ORIGIN)
    req.add_header("Access-Control-Request-Method", "GET")

    print("ASK4MO DEMO CORS\n")
    print(f"backend:\n{BACKEND_URL}\n")
    print(f"frontend origin:\n{FRONTEND_ORIGIN}\n")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            allow = resp.headers.get("Access-Control-Allow-Origin")
    except urllib.error.HTTPError as exc:  # preflight rejected → still has headers
        allow = exc.headers.get("Access-Control-Allow-Origin") if exc.headers else None
    except (urllib.error.URLError, OSError) as exc:
        print("backend reachable:\nNO")
        print(f"\nCould not reach {url} ({type(exc).__name__}). Start the backend first:")
        print("  uvicorn src.api.main:app --host 127.0.0.1 --port 8000")
        return 1

    if allow and (allow == "*" or allow.rstrip("/") == FRONTEND_ORIGIN):
        print(f"allow-origin:\n{allow}\n")
        print("DEMO CORS:\nREADY")
        return 0

    print(f"allow-origin:\n{allow or '(none returned)'}\n")
    print("DEMO CORS:\nNOT READY")
    print(
        f"\nThe backend does not allow the frontend origin {FRONTEND_ORIGIN}. Use the "
        "canonical demo port (frontend on http://localhost:3000, which the backend "
        "allows by default), or start the backend with the exact origin allow-listed:\n"
        f"  FRONTEND_ORIGINS={FRONTEND_ORIGIN} uvicorn src.api.main:app "
        "--host 127.0.0.1 --port 8000\n"
        "Never use a wildcard origin for anything but local demo convenience."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
