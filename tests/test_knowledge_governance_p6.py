"""Knowledge governance + K1–K4 datasets (Capstone P6). Deterministic, offline."""

from __future__ import annotations

import subprocess
import sys

from src.copilot.knowledge import governance as gov
from src.copilot.knowledge import governed_datasets as gd


# --- K1 compensation ---------------------------------------------------------

def test_k1_hit_carries_provenance_and_pay_unit():
    r = gd.lookup_compensation("Software developer")
    assert r.covered and r.median and r.currency == "EUR" and r.pay_unit == "gross_annual"
    assert r.reference_year and r.source_authority

def test_k1_abstains_outside_set_and_jurisdiction():
    assert gd.lookup_compensation("astronaut").abstained
    assert gd.lookup_compensation("astronaut").median is None  # never invents a salary
    assert gd.lookup_compensation("Software developer", jurisdiction="US").abstained


# --- K2 credentials ----------------------------------------------------------

def test_k2_differentiates_required_and_preferred():
    r = gd.lookup_credentials("registered_nurse", jurisdiction="DE")
    assert r.covered and r.regulated is True and r.required
    assert all(c.get("authority") and c.get("reference_year") for c in r.required)

def test_k2_abstains_outside_matrix():
    assert gd.lookup_credentials("astronaut", jurisdiction="DE").abstained
    assert gd.lookup_credentials("registered_nurse", jurisdiction="ZZ").abstained


# --- K3 aliases --------------------------------------------------------------

def test_k3_resolves_confident_alias_only():
    assert gd.resolve_alias("ML Engineer").canonical == "machine learning engineer"
    assert gd.resolve_alias("wizard of oz").resolved is False  # unknown stays unresolved


# --- K4 Adzuna capabilities --------------------------------------------------

def test_k4_validates_bounds_entitlement_and_allowlist():
    ok = gd.validate_adzuna_operation("salary_histogram", {"country": "DE", "role": "PM", "months": 12},
                                      entitlements={"PREMIUM_PREVIEW"})
    assert ok.valid and ok.live_validation_status == "UNVALIDATED"
    assert not gd.validate_adzuna_operation("salary_histogram", {"country": "DE", "role": "x", "months": 99},
                                            entitlements={"PREMIUM_PREVIEW"}).valid
    assert not gd.validate_adzuna_operation("salary_histogram", {"country": "DE", "role": "x"},
                                            entitlements=set()).valid
    assert not gd.validate_adzuna_operation("drop_tables", {}, entitlements={"PREMIUM_PREVIEW"}).valid


# --- governance manifest / readiness ----------------------------------------

def test_readiness_states_are_valid_and_deterministic():
    r = gov.overall_readiness()
    valid = {s.value for s in gov.ReadinessState}
    assert r["overall"] in valid and r["total_components"] >= 10
    assert all(c["state"] in valid for c in r["components"])

def test_manifest_unifies_governed_and_curated_sources():
    m = gov.knowledge_manifest()
    assert len(m["governed_datasets"]) == 4 and m["curated_source_count"] > 0

def test_coverage_matrix_does_not_claim_universal_coverage():
    cov = gov.coverage_matrix()
    assert cov["rows"] and "universal" in cov["disclaimer"].lower()

def test_language_boundary_separates_ui_from_kb_coverage():
    rows = {r["language"]: r for r in gov.language_boundary()}
    assert set(rows) == set(gov.SUPPORTED_LANGUAGES)
    assert rows["en"]["governed_kb_native_content"] == "full"
    assert rows["fr"]["governed_kb_native_content"] == "none"  # UI≠KB coverage
    assert rows["fr"]["ui_supported"] is True


# --- deterministic eval gate -------------------------------------------------

def test_knowledge_governance_eval_gate_passes():
    r = subprocess.run([sys.executable, "scripts/eval_knowledge_governance.py"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
