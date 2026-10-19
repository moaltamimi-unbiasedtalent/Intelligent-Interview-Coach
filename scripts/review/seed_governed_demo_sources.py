#!/usr/bin/env python
"""Register the SYNTHETIC capstone demonstration sources through the REAL Admin knowledge lifecycle (review environment only).

Register -> scan and parse (real worker) -> approve (human decision) -> index (real worker) -> activate -> test retrieval.
Every document is labelled SYNTHETIC CAPSTONE DEMONSTRATION DATA and is never an official, statistical, framework or industry source. Authority level 3, licence
class internal_owned, publisher text says so. Idempotent: a title that already exists is skipped. The backend and the job worker must both be running with the SAME
DATABASE_URL and COPILOT_DATA_DIR, and the backend refuses real scanning only if MALWARE_SCAN_REQUIRED is set; this review environment uses FILE_SCAN_PROVIDER=fake,
a development-only scanner that must never be used in staging or production.

    python scripts/review/seed_governed_demo_sources.py --base http://127.0.0.1:8020 --email admin.demo@example.invalid --password-file /tmp/ask4mo_admin_login.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/capstone/p10/pilot2/fixtures/knowledge/pilot_knowledge_v1.json"
LABEL = "SYNTHETIC CAPSTONE DEMONSTRATION DATA"
PUBLISHER = f"{LABEL} (not an official, statistical, framework or industry source)"


def doc_text(src: dict) -> str:
    chunks = [c if isinstance(c, str) else c.get("text", "") for c in src["chunks"]]
    return f"[{LABEL}] {src['title']}\n\n" + "\n\n".join(chunks) + "\n"


def find(c: httpx.Client, base: str, title: str) -> dict | None:
    for s in c.get(f"{base}/api/v1/admin/knowledge/sources?page_size=100").json().get("items", []):
        if s["title"] == title:
            return s
    return None


ACTIONS = {"review_required": "approve", "approved": "index", "indexed": "activate"}


def drive(c: httpx.Client, base: str, title: str, timeout: float = 120.0) -> dict:
    """Advance one source through the lifecycle, resuming from whatever state it is in (idempotent)."""
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        item = find(c, base, title)
        if item is None:
            raise SystemExit(f"source vanished: {title}")
        state = item["state"]
        if state != last:
            print(f"    state: {state} (scan {item.get('scan_status')}, chunks {item.get('chunk_count')})")
            last = state
        if state == "active":
            return item
        if item.get("failure_category"):
            raise SystemExit(f"FAILED: {item['failure_category']}")
        step = ACTIONS.get(state)
        if step:
            r = c.post(f"{base}/api/v1/admin/knowledge/versions/{item['version_public_id']}/{step}")
            print(f"  {step}: {r.status_code}")
            if r.status_code >= 300:
                raise SystemExit(f"{step} refused: {r.text[:200]}")
            last = None
        time.sleep(2)
    raise SystemExit(f"timeout driving {title}; is the job worker running with the same DATABASE_URL and COPILOT_DATA_DIR?")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8020")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password-file", required=True, help="a file whose line 2 is 'password: <value>' (never printed)")
    a = ap.parse_args(argv)
    password = Path(a.password_file).read_text().splitlines()[1].split(" ", 1)[1].strip()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with httpx.Client(timeout=30.0) as c:
        r = c.post(f"{a.base}/api/v1/auth/login", json={"email": a.email, "password": password})
        if r.status_code != 200:
            print(f"login failed: {r.status_code}")
            return 2
        for src in fixture["sources"]:
            title = f"[SYNTHETIC CAPSTONE DEMO] {src['title']}"
            if find(c, a.base, title) is None:
                print(f"register: {title}")
                r = c.post(f"{a.base}/api/v1/admin/knowledge/sources", data={"title": title, "language": "en", "authority_level": "3", "publisher": PUBLISHER,
                                                                               "provenance_note": f"{LABEL}. Written for the capstone review; not verified external guidance.", "licence_class": "internal_owned"},
                           files={"file": (f"{src['source_id']}.txt", doc_text(src).encode(), "text/plain")})
                if r.status_code != 201:
                    print(f"  upload refused: {r.status_code} {r.text[:200]}")
                    return 3
            else:
                print(f"resume: {title}")
            drive(c, a.base, title)
        rd = c.get(f"{a.base}/api/v1/admin/knowledge/readiness").json()
        act = c.get(f"{a.base}/api/v1/admin/knowledge/active").json()
        print("readiness:", json.dumps(rd, default=str)[:500])
        print("active:", json.dumps(act, default=str)[:300])
        t = c.post(f"{a.base}/api/v1/admin/knowledge/test-retrieval", json={"query": "How do I structure a behavioural interview answer with the STAR method?"})
        print("test retrieval:", t.status_code, json.dumps(t.json(), default=str)[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
