"""Operator CLI and local spending indicator for the capstone live demonstration (EUR 10.00 approved cap).

    python scripts/demo/live_budget.py status|init|kill|resume|recent|plan
    python scripts/demo/live_budget.py release-reserve --yes     # owner decision: allow spend past the EUR 8.00 operating stop
    python scripts/demo/live_budget.py serve [--port 8030]       # read-only indicator on 127.0.0.1 with a KILL button

The ledger lives outside the repository (ASK4MO_DEMO_LEDGER_DIR, default /tmp/ask4mo_live_demo/ledger). Figures are our own
conservative estimates, not provider charges.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.demo_live.budget import DemoBudget, DemoBudgetError, load_authorization, load_pricing  # noqa: E402

DEFAULT_DIR = "/tmp/ask4mo_live_demo/ledger"


def _open() -> DemoBudget:
    return DemoBudget(os.environ.get("ASK4MO_DEMO_LEDGER_DIR", DEFAULT_DIR), load_authorization())


def _plan() -> dict:
    a = load_authorization()
    return {"cap_eur": "10.00", "operating_stop_eur": "8.00", "category_allocations_eur": {"agent": "2.00", "interview": "2.00", "ragas": "3.00", "troubleshooting": "1.00", "safety_reserve": "2.00"}, "limits": vars(a.limits), "models_priced": sorted(load_pricing()),
            "abort_conditions": ["kill switch file present", "EUR 8.00 operating stop", "EUR 10.00 hard cap", "category allocation exhausted", "request cap", "usage above reservation (overrun engages the kill switch)", "CI environment"]}


PAGE = """<!doctype html><meta charset=utf-8><title>Demo spend</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>body{font:15px system-ui;margin:24px;max-width:640px}td{padding:2px 12px 2px 0}.k{color:#b00;font-weight:700}.ok{color:#070}</style>
<h2>Ask4Mo live demo spend (EUR, estimates)</h2><div id=s>loading</div><p><button onclick="fetch('/kill',{method:'POST'}).then(load)">KILL SWITCH</button></p>
<script>function load(){fetch('/status').then(r=>r.json()).then(j=>{let c=Object.entries(j.categories).map(([k,v])=>`<tr><td>${k}</td><td>${v.held_eur} / ${v.cap_eur}</td></tr>`).join('');
document.getElementById('s').innerHTML=`<p class="${j.kill_switch?'k':'ok'}">${j.kill_switch?'KILLED - no provider requests':'Active'}</p><table><tr><td>Cap</td><td>${j.cap_eur}</td></tr><tr><td>Operating stop</td><td>${j.operating_stop_eur}</td></tr><tr><td>Settled</td><td>${j.settled_eur}</td></tr><tr><td>Reserved (open)</td><td>${j.reserved_open_eur}</td></tr><tr><td>Unknown outcome held</td><td>${j.unknown_held_eur}</td></tr><tr><td><b>Remaining to cap</b></td><td><b>${j.remaining_to_cap_eur}</b></td></tr><tr><td>Requests</td><td>${j.requests}</td></tr></table><table>${c}</table><p>${j.note}</p>`})}load();setInterval(load,3000)</script>"""


def serve(port: int) -> None:
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            if self.path == "/status":
                b = _open()
                try:
                    self._send(200, json.dumps(b.summary()))
                finally:
                    b.close()
            else:
                self._send(200, PAGE, "text/html")

        def do_POST(self):
            if self.path == "/kill":
                b = _open()
                b.kill("indicator button")
                b.close()
                self._send(200, "{}")
            else:
                self._send(404, "{}")

        def log_message(self, *a):
            pass

    print(f"indicator on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "init", "kill", "resume", "recent", "plan", "release-reserve", "serve"])
    ap.add_argument("--port", type=int, default=8030)
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args()
    try:
        if ns.cmd == "plan":
            print(json.dumps(_plan(), indent=2))
            return 0
        if ns.cmd == "serve":
            serve(ns.port)
            return 0
        b = _open()
        if ns.cmd == "kill":
            b.kill("operator CLI")
        elif ns.cmd == "resume":
            b.resume()
        elif ns.cmd == "release-reserve":
            if not ns.yes:
                print("Refusing: pass --yes only on the Product Owner's explicit decision.")
                return 2
            b.release_reserve()
        if ns.cmd == "recent":
            print(json.dumps(b.recent(20), indent=2))
        else:
            print(json.dumps(b.summary(), indent=2))
        b.close()
    except DemoBudgetError as e:
        print(f"FAIL CLOSED: {e.reason}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
