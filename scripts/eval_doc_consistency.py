#!/usr/bin/env python
"""P10B-W9.11 documentation/architecture consistency guard (deterministic, offline, 0 paid/live calls).

Small, targeted invariants where documentation drift is high-risk: authority-level semantics, locale vs
speech language sets, specialist names, tool-registry composition, and presence of the current-state
statements (auth, PRIV limitations) in the canonical documents. Runtime code is the source of truth; a failure
means a document (or comment) drifted from the code, never that the code should change to match a document.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast, isolated research cache).
import tests.conftest  # noqa: E402,F401


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def norm(text: str) -> str:
    """Collapse whitespace and markdown emphasis so line wrapping/bold never breaks a phrase check."""
    return re.sub(r"[\s*`]+", " ", text)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    # 1. Authority-level semantics: 1 official/statistical, 2 public/professional framework, 3 industry.
    from src.copilot import constants as c

    check("authority_constants_canonical",
          (c.AUTHORITY_OFFICIAL, c.AUTHORITY_PUBLIC_FRAMEWORK, c.AUTHORITY_INDUSTRY) == (1, 2, 3), "1/2/3")
    schema = read("src/api/schemas/career.py")
    check("authority_comment_not_reversed",
          "1=official" in schema and "3=reputable" in schema and "1=industry" not in schema and "3=official" not in schema,
          "src/api/schemas/career.py")
    reversed_docs = [p for p in ("docs/knowledge_architecture.md", "docs/knowledge_source_catalogue.md",
                                 "docs/sprint4_architecture.md", "README.md")
                     if re.search(r"1\s*=\s*industry|3\s*=\s*official", read(p), re.I)]
    check("authority_docs_not_reversed", not reversed_docs, ", ".join(reversed_docs) or "clean")

    # 2. Locale vs speech language dimensions.
    from src.locales import DOCUMENT_LANGUAGE_CODES, SUPPORTED_LOCALE_CODES
    from src.voice.realtime import SUPPORTED_REALTIME_LOCALES

    tts = re.search(r"SUPPORTED_TTS_LOCALES[^=]*=\s*\[([^\]]*)\]", read("frontend/lib/speech/ttsLocales.ts"))
    tts_codes = re.findall(r'"([a-z]{2})"', tts.group(1)) if tts else []
    dict_codes = re.findall(r'code:\s*"([a-z]{2})-', read("frontend/components/ui/DictationControl.tsx"))
    check("locale_and_speech_counts",
          len(SUPPORTED_LOCALE_CODES) == 8 and len(SUPPORTED_REALTIME_LOCALES) == 7 and len(tts_codes) == 7
          and len(dict_codes) == 7 and len(DOCUMENT_LANGUAGE_CODES) == 7,
          f"locales {len(SUPPORTED_LOCALE_CODES)}, realtime {len(SUPPORTED_REALTIME_LOCALES)}, tts {len(tts_codes)}, "
          f"dictation {len(dict_codes)}, document {len(DOCUMENT_LANGUAGE_CODES)}")
    check("russian_not_a_speech_language",
          "ru" not in SUPPORTED_REALTIME_LOCALES and "ru" not in tts_codes and "ru" not in dict_codes, "ru excluded")
    readme = read("README.md")
    check("readme_states_locale_vs_speech",
          all(code in readme for code in SUPPORTED_LOCALE_CODES) and re.search(r"Eight\s+\*\*interface locales\*\*", readme)
          and re.search(r"seven\s+languages", readme) and "not an official ESCO language" in readme,
          "README distinguishes 8 interface locales from 7 speech languages")

    # 3. Specialists: exactly three, no evaluation specialist, documented by name.
    from src.agent.specialists.registry import SpecialistName

    names = sorted(m.value for m in SpecialistName)
    check("specialists_exactly_three_no_evaluation",
          names == ["candidate_evidence", "interview_strategy", "role_opportunity"], ", ".join(names))
    arch = read("docs/sprint4_architecture.md")
    check("docs_name_all_specialists_and_deny_evaluation",
          all(n in readme and n in arch for n in names) and "no Evaluation specialist" in norm(arch)
          and "not a specialist or an agent" in norm(readme),
          "README + architecture overview")

    # 4. Tool registry composition (derived from code, not hard-coded in many docs).
    from src.agent.registry import career_tool_registry

    reg = career_tool_registry(MagicMock())
    tools = reg.names()
    spec_tools = {"AnalyzeRoleOpportunity", "FindCandidateEvidence", "BuildCoachingStrategy"}
    human = {"ProposePreparationMemory", "RequestPracticeHandoff"}
    career = [t for t in tools if t not in spec_tools and t not in human]
    check("tool_registry_composition",
          len(career) == 6 and spec_tools <= set(tools) and human <= set(tools) and len(tools) == 11,
          f"{len(career)} career + {len(spec_tools)} specialist + {len(human)} human-action = {len(tools)}")
    check("docs_describe_registry_composition",
          "six Career tools" in norm(readme) and "six Career tools" in norm(arch),
          "README and architecture overview match the registry")

    # 5. Current-state statements in canonical docs.
    privacy = read("docs/privacy.md")
    check("readme_auth_not_stale",
          "Production **OIDC** is not implemented" not in readme and "fail-closed" in readme and "HttpOnly" in readme
          and "not validated live" in readme or "has not been validated live" in readme,
          "README documents session auth and OIDC status")
    check("privacy_doc_current",
          "Auth via Streamlit OIDC" not in privacy and "/account/data" in privacy
          and "PRIV-W9-01" in privacy and "PRIV-W9-02" in privacy and "not legal advice" in norm(privacy),
          "docs/privacy.md reflects W9.8 and keeps both limitations")
    check("readme_limitations_state_priv_items_closed_with_limits", "PRIV-W9-01" in readme and "PRIV-W9-02" in readme and "closed in W10.10" in readme and "never back-filled" in readme, "README (closed in W10.10, stated limits)")
    check("admin_current_vs_planned_documented",
          "qualified in W10.14" in readme and "Not built:" in readme and "W10.14" in arch and "Superseded by P10B-W10" in arch, "README + architecture state the Admin control plane as implemented and qualified, with the not-built list")
    check("docs_index_exists", "Documentation map" in read("docs/README.md"), "docs/README.md")
    check("retention_note_scoped_to_streamlit",
          "legacy Streamlit interface" in read("src/constants.py").split("DATA_RETENTION_NOTE")[0][-500:], "constants comment")
    return out


def main() -> int:
    print("ASK4MO - P10B-W9.11 DOCUMENTATION / ARCHITECTURE CONSISTENCY\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:44s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
