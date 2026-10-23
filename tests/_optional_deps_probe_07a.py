"""Subprocess probe for tests/test_optional_dependencies_07a.py: a FRESH interpreter in which every optional extra is unimportable (``sys.modules[name] = None``, exactly how
an absent package behaves), then imports the application, builds the real app and exercises the surfaces that use an optional extra. Prints one JSON line.

Run only through the test (it imports ``tests.conftest`` first: temp database, no ``.env``, no development store is ever opened)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BLOCKED = json.loads(sys.argv[1])


# ``sys.modules[name] = None`` is how an absent package behaves for ``import`` (ImportError) and for ``importlib.util.find_spec`` (None).
for _name in BLOCKED:
    sys.modules[_name] = None

import tests.conftest  # noqa: E402,F401  (isolation first: temp DB, no .env)

result: dict = {}
from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import create_app  # noqa: E402

app = create_app()
with TestClient(app) as client:
    for label, path in (("health", "/api/health"), ("capabilities", "/api/capabilities"), ("speech_capabilities", "/api/v1/speech/capabilities"),
                        ("realtime_status", "/api/v1/voice/realtime/status"), ("documents", "/api/v1/documents"), ("model_profiles", "/api/v1/model-profiles")):
        result[label] = client.get(path).status_code

from src.documents.ocr import TesseractOcrEngine, ocr_runtime_status  # noqa: E402

result["ocr_available"] = TesseractOcrEngine().is_available()
result["ocr_status_available"] = bool(ocr_runtime_status().get("available"))

from src.application.admin_command_center import repository_head  # noqa: E402

result["alembic_head"] = repository_head()

from src.copilot.evaluation.ragas_adapter import ragas_available  # noqa: E402

result["ragas_available"] = ragas_available()

leaked = sorted(m for m in sys.modules if any(m == b or m.startswith(b + ".") for b in BLOCKED) and sys.modules[m] is not None)   # anything real imported despite the block
result["blocked_modules_present"] = leaked
print("PROBE_RESULT " + json.dumps(result))
