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


def test_only_package_1_core_is_authorised_and_nothing_is_runtime_approved():
    d = mod.load()
    assert not any(e["runtime_authorized"] for e in d["entries"])
    assert {e["id"] for e in d["entries"] if e["acquisition_authorized"]} == {"us_soc_2018", "us_bls_oews"}
    assert [p["approved"] for p in d["acquisition_packages"]] == [True] + [False] * 6
    assert {x["id"] for x in d["owner_decisions"] if x["owner_decision"]} == set(mod.RECORDED_DECISIONS)


def test_ilostat_not_auto_c3():
    e = next(x for x in mod.load()["entries"] if x["id"] == "intl_ilostat")
    assert e["proposal"]["precedence_category"] == "UNKNOWN" and "D-16" in e["decisions"]
