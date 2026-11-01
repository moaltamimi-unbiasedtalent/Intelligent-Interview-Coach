"""Sanitized refusal evidence rejects malformed, oversized and non-allowlisted records."""
import json

from scripts.e2e.data_export_connected import refusal_evidence


def test_bounded_refusal_evidence(tmp_path):
    path = tmp_path / "facts.jsonl"
    assert refusal_evidence(path) == []
    record = {"scenario": "anonymous", "status": 401, "classification": "unauthorized", "envelope_valid": True,
              "export_absent": True, "attachment_absent": True, "logout_success": None, "passed": True}
    path.write_text(json.dumps(record) + "\n")
    assert refusal_evidence(path) == [record]
    for invalid in ({**record, "secret": "SYNTH_PRIVATE_SECRET_CANARY"}, {**record, "status": "401"},
                    {**record, "classification": "raw"}, {**record, "passed": "yes"}):
        path.write_text(json.dumps(invalid) + "\n")
        assert refusal_evidence(path) == []
    path.write_text("not json")
    assert refusal_evidence(path) == []
    path.write_text("x" * 2049)
    assert refusal_evidence(path) == []
