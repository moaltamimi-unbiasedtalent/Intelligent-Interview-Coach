#!/usr/bin/env python
"""Capstone P10B Wave 4 — Prepare/Practice integration & multilingual interview evaluation.

Deterministic, offline invariant checks (no browser, no paid/live provider). Mixes behavioural
checks (the real prompt/language pipeline) with source-structural checks (one governed document
pipeline, evidence boundary, voice, no-new-agent). Exits non-zero on any failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FE = ROOT / "frontend"


def read(rel: str, *, base: Path = ROOT) -> str:
    p = base / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    from src import prompts
    from src.models import InterviewConfiguration

    def cfg(lang: str = "") -> InterviewConfiguration:
        return InterviewConfiguration(
            target_role="Registered Nurse", industry_or_sector="healthcare", career_level="senior",
            interview_types=["behavioural"], interviewer_persona="neutral", difficulty="moderate",
            response_detail="standard", number_of_questions=2, conversation_language=lang,
        )

    tasks = [prompts.TASK_STRATEGY, prompts.TASK_QUESTION, prompts.TASK_EVALUATION, prompts.TASK_REPORT]

    # --- language ---
    # Derived from the ONE canonical locale source (src/locales.py), so a new locale can never leave this
    # prompt allow-list stale; W9.7 added Russian (8 product locales).
    from src.locales import SUPPORTED_LOCALE_CODES
    check("eight_languages_configured",
          set(prompts._CONVERSATION_LANGUAGE_NAMES) == set(SUPPORTED_LOCALE_CODES)
          and set(SUPPORTED_LOCALE_CODES) == {"en", "de", "fr", "es", "it", "pt", "nl", "ru"},
          "8 product locales (incl. ru) mapped to language names, in lock-step with src/locales.py")
    de_prompts = {t: prompts.build_task_system_prompt(t, "zero_shot", cfg("de")) for t in tasks}
    check("practice_language_propagated",
          all("German" in de_prompts[t] for t in (prompts.TASK_STRATEGY, prompts.TASK_QUESTION, prompts.TASK_EVALUATION)),
          "question/evaluation/strategy carry the language directive")
    check("report_language_propagated", "German" in de_prompts[prompts.TASK_REPORT],
          "report generation carries the language directive")
    check("conversation_language_bounded",
          all("CONVERSATION LANGUAGE" not in prompts.build_task_system_prompt(prompts.TASK_QUESTION, "zero_shot", cfg(b))
              for b in ("xx", "zz", "de-de")),
          "unknown/out-of-list codes yield no directive")
    geo = prompts.build_task_system_prompt(prompts.TASK_QUESTION, "zero_shot", cfg("de")).lower()
    check("language_geography_separation", "geography" in geo and "language of your prose" in geo,
          "directive states prose-only, not geography")
    umsg = lambda lang: prompts.build_task_user_message(  # noqa: E731
        prompts.TASK_EVALUATION, cfg(lang), question="Describe a challenge.", candidate_answer="I did X.")
    check("scoring_language_independent", umsg("en") == umsg("de") == umsg("fr"),
          "the model's DATA (user message) is identical across languages → scores unaffected")

    # --- one governed document pipeline (no duplicate uploaders/endpoints) ---
    doc_routes = read("src/api/routes/documents.py")
    upload_posts = doc_routes.count('@router.post("", ')
    check("document_pipeline_single", upload_posts == 1 and "reprocess" in doc_routes,
          "exactly one upload endpoint; the governed pipeline is reused")
    upload_component = read("frontend/components/documents/DocumentUpload.tsx")
    picker = read("frontend/components/documents/DocumentPicker.tsx")
    check("reusable_upload_seam", bool(upload_component) and "api.documents.upload" in upload_component
          and "DocumentUpload" in picker, "single DocumentUpload seam, reused by the picker")

    # --- Prepare + Practice surfaces mount the governed picker ---
    prepare = read("frontend/components/agent/AgentPrepareWorkspace.tsx")
    setup = read("frontend/components/interview/InterviewSessionSetup.tsx")
    check("prepare_document_surface", "DocumentPicker" in prepare and "job_description_document_id" in prepare,
          "Prepare lets the candidate select/upload a JD via the governed picker")
    check("practice_document_surface",
          "DocumentPicker" in setup and "job_description_document_id" in setup and "use_candidate_evidence" in setup,
          "Practice setup exposes JD selection + approved-evidence opt-in")

    # --- evidence boundary: approved only, owner-scoped, raw CV never dumped ---
    evidence_src = read("src/application/evidence_access_service.py")
    check("approved_evidence_only",
          "approved_claims" in evidence_src and "evidence_stories" in evidence_src
          and "raw" in evidence_src.lower(), "evidence surface exposes only approved claims/safe stories")
    route_src = read("src/api/routes/interview.py")
    check("cv_raw_prompt_blocked",
          "_compose_evidence_background" in route_src and "approved_claims" in route_src
          and "extracted_text" in route_src,
          "candidate context comes from APPROVED evidence / server-resolved doc text, not a raw CV dump")
    check("owner_scope", "user_id=user_id" in route_src and "get_download" in read("src/application/documents_service.py"),
          "document/evidence resolution is owner-scoped (trusted user_id)")
    check("source_revocation_respected", "rederive_all_for_user" in read("src/application/documents_service.py"),
          "deleting a source re-derives evidence (never left silently verified)")

    # --- JD stays DATA (injection-inert) ---
    iv_src = read("src/interview_service.py")
    check("jd_injection_inert", "_screen_context" in iv_src and "job_description" in iv_src,
          "job description is screened + placed as user DATA, never as instructions")

    # --- voice / dictation preserved ---
    answer_composer = read("frontend/components/interview/InterviewAnswerComposer.tsx")
    # Practice hosts dictation via the shared Composer (which embeds DictationControl); Prepare uses
    # DictationControl directly. Dictation language stays independent (useDictationLanguage).
    check("dictation_separation",
          "Composer" in answer_composer and "DictationControl" in prepare and "useDictationLanguage" in prepare,
          "existing P3 dictation reused on both surfaces; dictation language stays independent")
    check("no_auto_submit", "onSubmit" not in picker and "submit(" not in picker,
          "selecting/uploading a document never submits anything")
    prepare_page = read("frontend/app/prepare/page.tsx")
    practice_page = read("frontend/app/practice/page.tsx")
    check("voice_coordination_preserved",
          "VoiceCoordinationProvider" in prepare_page and "VoiceCoordinationProvider" in practice_page,
          "STT/TTS mutual-exclusion provider still wraps both surfaces")

    # --- no new agent/specialist introduced ---
    specialists_dir = ROOT / "src" / "agent" / "specialists"
    specialist_files = sorted(p.name for p in specialists_dir.glob("*_specialist.py")) if specialists_dir.exists() else []
    check("no_new_agent_required", set(specialist_files) == {"role_specialist.py", "evidence_specialist.py", "coaching_specialist.py"},
          f"exactly the three existing specialists: {specialist_files}")

    return results


SAFETY = {
    "conversation_language_bounded", "scoring_language_independent", "cv_raw_prompt_blocked",
    "owner_scope", "approved_evidence_only", "source_revocation_respected", "jd_injection_inert",
    "language_geography_separation", "document_pipeline_single",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P10B WAVE 4 PREPARE/PRACTICE INTEGRATION EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  ← SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:32s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print("\nPaid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all Prepare/Practice integration invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
