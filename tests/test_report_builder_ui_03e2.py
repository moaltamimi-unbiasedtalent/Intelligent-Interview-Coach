"""03E2 (views): the one backend change of the Reports UI package. The export UI reads the file name and row count the audited export response carries, so a
cross-origin browser must be ALLOWED to read them (CORS exposes only listed response headers). Nothing else changed in the backend by this PR."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.config import ApiSettings
from src.api.main import create_app

ORIGIN = "http://localhost:3128"


def test_cors_exposes_the_export_file_name_and_row_count_to_the_allowed_origin_only():
    app = create_app(ApiSettings(env="test", frontend_origins=(ORIGIN,)))
    with TestClient(app) as c:
        ok = c.get("/api/v1/health", headers={"Origin": ORIGIN})
        bad = c.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    exposed = {h.strip().lower() for h in ok.headers["access-control-expose-headers"].split(",")}
    assert {"x-request-id", "content-disposition", "x-export-rows"} <= exposed
    assert bad.headers.get("access-control-allow-origin") != "http://evil.example"
