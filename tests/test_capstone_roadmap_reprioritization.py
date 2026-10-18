"""Documentation consistency for the 2026-10-18 Capstone reprioritisation: no workstream is removed, the decision and the revised order are recorded, and nothing is claimed complete that is not."""

from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs/capstone"
ROADMAP = (DOCS / "ASK4MO_MASTER_CAPSTONE_ROADMAP.md").read_text(encoding="utf-8")
PLAN = (DOCS / "capstone_phase_plan.md").read_text(encoding="utf-8")
BACKLOG = (DOCS / "p10/P10C_F2A_POST_SUBMISSION_BACKLOG.md").read_text(encoding="utf-8")
WORKSTREAMS = ["**P10C**", "**P10D**", "**W12.4E**", "**W12.4F**", "**W12.5**", "**P10E**", "**Integrated Candidate/Admin/Operations Requalification**", "**RC-P10-004**", "**P10F**", "**AC-24**", "**P11**"]
ORDER = ["P10C-G", "P10D", "W12.4E", "W12.4F", "W12.5", "P10E", "Integrated Candidate/Admin/Operations Requalification", "RC-P10-004", "AC-24", "P11 Final Capstone Submission"]


def _table_rows():
    return [line for line in ROADMAP.splitlines() if line.startswith("| **")]


def test_every_workstream_row_is_still_present():
    rows = _table_rows()
    for w in WORKSTREAMS:
        assert any(r.startswith(f"| {w}") for r in rows), w


def test_the_deferrals_are_recorded_on_the_rows_with_the_earlier_state_kept():
    p10c = next(r for r in _table_rows() if r.startswith("| **P10C**"))
    p10f = next(r for r in _table_rows() if r.startswith("| **P10F**"))
    assert "PARTIALLY ENGINEERING COMPLETE: REMAINING P10C-F WORK DEFERRED UNTIL AFTER CAPSTONE SUBMISSION" in p10c and "Earlier recorded state: IN PROGRESS" in p10c
    assert "DEFERRED UNTIL AFTER CAPSTONE SUBMISSION" in p10f and "Earlier recorded state: NOT STARTED" in p10f
    assert "P10C-F1 governance" in ROADMAP and "P10C-F2A" in ROADMAP


def test_the_revised_order_and_the_decision_record_exist_in_both_documents():
    for doc in (ROADMAP, PLAN):
        pos = [doc.index(item, doc.index("Revised pre-submission order")) for item in ORDER]
        assert pos == sorted(pos), "the revised pre-submission order must be recorded in sequence"
    assert "2026-10-18" in ROADMAP and "not evidence qualification, runtime authorisation, legal clearance or production approval" in ROADMAP


def test_no_mandatory_criterion_is_marked_passed_by_the_decision():
    assert "AC-24** acceptance closure" in ROADMAP and "stays PARTIAL" in ROADMAP
    assert "No mandatory release criterion is marked passed" in ROADMAP
    assert "BELOW GATE" in ROADMAP and "93.7%" in ROADMAP and "RB-LIC-1" in ROADMAP
    assert "all 12 gates False" in ROADMAP.split("Capstone roadmap reprioritisation")[-1]


def test_every_deferred_obligation_is_in_the_backlog():
    for item in ("P10C-F2B United Kingdom", "P10C-F2C ESCO/ISCO", "P10C-F2D Germany and EU", "P10C-F2E Canada, Mexico, Brazil", "P10C-F2F wider South America", "Human measurement and alias reviews",
                 "reviewer appointments", "persistent source authorisation", "commercial licensing clearance", "Compensation V2 runtime authorisation", "P10F targeted human validation"):
        assert item in BACKLOG, item
    assert "retained regardless of the P10F deferral" in BACKLOG
