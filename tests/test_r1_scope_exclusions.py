"""Phase 00 review: machine evidence that the capabilities behind the proposed R1.0 reclassification are inaccessible to Candidates (API and UI).

Evidence keys (docs/production/PRODUCTION_ISSUE_RECONCILIATION.json: scope_proposals.evidence) are verified here. Offline, read-only, no provider. The test also records the
limit of the proof: curated US sources remain reachable by Candidates, which the reclassification does NOT exclude (package 02D, OD-US-CONTENT).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECON = json.loads((ROOT / "docs/production/PRODUCTION_ISSUE_RECONCILIATION.json").read_text(encoding="utf-8"))
REGISTER = {i["original_id"]: i for i in json.loads((ROOT / "docs/capstone/post_submission_deferred_issues.json").read_text(encoding="utf-8"))["issues"]}


def test_e_import_no_runtime_module_imports_the_knowledge_foundation():
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("src/knowledge_foundation/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            if any(n == "src.knowledge_foundation" or n.startswith("src.knowledge_foundation.") for n in names):
                offenders.append(rel)
    assert offenders == []


def test_e_routes_no_non_admin_or_admin_route_exposes_compensation_foundation_or_recording():
    import tests.conftest  # noqa: F401  (isolation)
    from src.api.config import ApiSettings
    from src.api.main import create_app

    paths = sorted(create_app(ApiSettings(env="test", frontend_origins=("http://localhost:3000",))).openapi()["paths"])
    assert len(paths) > 200
    hits = [p for p in paths if any(k in p.lower() for k in ("compensation", "foundation", "qualif", "alias", "us-soc", "recording"))]
    assert hits == []


def test_e_ui_no_frontend_source_references_the_foundation_or_compensation_v2():
    needles = ("compensation_v2", "compensationv2", "compensation-v2", "knowledge_foundation", "us_soc", "bls_oews", "alias_review")
    offenders = []
    for base in ("app", "components", "lib"):
        for path in (ROOT / "frontend" / base).rglob("*"):
            if path.suffix in (".ts", ".tsx") and path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                if any(n in text for n in needles):
                    offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_e_ready_the_foundation_reports_it_is_not_operational():
    from src.knowledge_foundation.readiness import assess

    out = assess()
    assert out.get("operational_today") is False or out.get("compensation_v2", {}).get("operational_today") is False or _find(out, "operational_today") is False
    assert _find(out, "compensation_v2_records_linkable_today") in (0, None) and _find(out, "approved_compensation_v2_sources") in (0, None)


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find(v, key)
            if found is not None:
                return found
    return None


def test_e_register_each_proposed_item_states_no_candidate_effect_while_disabled():
    for k, v in RECON["scope_proposals"]["reclassification"].items():
        if "E-REGISTER" in v["evidence"]:
            impact = REGISTER[k]["candidate_impact"].lower()
            assert "none while compensation v2" in impact or "no v2 result reaches candidates" in impact, k


def test_e_speech_the_frontend_has_no_server_transcription_client_and_gates_are_false():
    sources = []
    for base in ("lib", "components", "app"):
        for path in (ROOT / "frontend" / base).rglob("*"):
            if path.suffix in (".ts", ".tsx") and path.is_file() and ".test." not in path.name:
                sources.append(path.read_text(encoding="utf-8", errors="ignore"))
    joined = "\n".join(sources)
    assert "/speech/transcriptions" not in joined and "/speech/synthesis" not in joined and "/speech/capabilities" in joined
    from src.speech import policy

    assert policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED is False and policy.WHISPER_API_TRANSPORT_AUTHORIZED is False and policy.MODEL_DOWNLOADS_AUTHORIZED is False


def test_the_proposal_is_not_applied_and_the_two_failed_proofs_stay_in_r1_0():
    sp = RECON["scope_proposals"]
    assert sp["applied"] is False and len(sp["reclassification"]) == 10 and set(sp["withdrawn"]) == {"BL-6.6", "BL-7"}
    by = {r["id"]: r for r in RECON["items"]}
    assert all(by[k]["disposition"] == "FIX BEFORE R1.0" and by[k]["release"] == "R1.0" for k in list(sp["reclassification"]) + list(sp["withdrawn"]))
    assert all(v["proposed_release"] in ("R1.4", "R1.5", "R1.6") for v in sp["reclassification"].values())
    assert all(h in by for h in sp["reclassification"])                                           # historical IDs preserved


def test_limit_of_the_proof_curated_us_sources_remain_in_the_candidate_corpus():
    """Not a defect marker: it records why excluding unqualified US claims is package 02D, not the reclassification."""
    from src.copilot.knowledge import manifest as km

    ids = {e.source_id for e in km.load_manifest()}
    assert {"onet", "bls_ooh"} <= ids or any(i.startswith("bls") for i in ids)
    doc = (ROOT / "docs/production/execution/R1_SCOPE_RECLASSIFICATION_PROPOSAL.md").read_text(encoding="utf-8")
    assert "02D" in doc and "OD-US-CONTENT" in doc and "NOT excluded" in doc
