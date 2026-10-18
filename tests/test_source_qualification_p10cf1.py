"""P10C-F1: the source dossier is consistent, complete and approves nothing."""
import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts/p10c_f1_dossier.py"
_s = importlib.util.spec_from_file_location("p10c_f1_dossier", _p)
mod = importlib.util.module_from_spec(_s)
_s.loader.exec_module(mod)


def test_dossier_valid_and_docs_match():
    d = mod.load()
    assert mod.validate(d) == []
    assert mod.DOCS["approval"].read_text() == mod.render_approval(d)
    assert mod.DOCS["packages"].read_text() == mod.render_packages(d)


def test_nothing_approved():
    d = mod.load()
    assert all(e["approval_status"] == "NOT_APPROVED" and not e["runtime_authorized"] and not e["acquisition_authorized"] for e in d["entries"])
    assert not any(p["approved"] for p in d["acquisition_packages"])
    assert all(x["owner_decision"] is None for x in d["owner_decisions"])


def test_ilostat_not_auto_c3():
    e = next(x for x in mod.load()["entries"] if x["id"] == "intl_ilostat")
    assert e["proposal"]["precedence_category"] == "UNKNOWN" and "D-16" in e["decisions"]
