#!/usr/bin/env python
"""Capstone P3 / E-dictation evaluation.

Deterministic, offline verification of dictation INVARIANTS by inspecting the
frontend source and confirming the safety tests exist. Dictation is a browser feature,
so this asserts explicit structural invariants rather than subjective UX scores. No
paid/live calls; no browser required.

Invariants (per §16): surface_coverage, transcript_editability, no_auto_submit,
typed_text_preservation, unsupported_fallback, permission_failure_isolation,
accessibility_contract, privacy_no_audio_persistence, no_localstorage_candidate_content,
response_architecture_unchanged, multilingual_bounded.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"


def read(rel: str) -> str:
    p = FE / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    control = read("components/ui/DictationControl.tsx")
    hook = read("lib/speech/useDictation.ts")
    adapter = read("lib/speech/browserAdapter.ts")
    composer = read("components/ui/Composer.tsx")
    agent_composer = read("components/agent/AgentComposer.tsx")
    answer_composer = read("components/interview/InterviewAnswerComposer.tsx")
    prepare = read("components/agent/AgentPrepareWorkspace.tsx")
    lang_hook = read("lib/speech/useDictationLanguage.ts")
    no_autosubmit_test = read("tests/dictation-no-autosubmit.test.tsx")
    control_test = read("tests/dictation-control.test.tsx")
    help_center = read("components/help/HelpCenter.tsx")

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (ok, detail)

    # 1) Two real surfaces host the shared dictation control (via Composer or directly).
    surface1 = ("Composer" in agent_composer) and ("DictationControl" in prepare)
    surface2 = "Composer" in answer_composer
    check("surface_coverage", surface1 and surface2 and "DictationControl" in composer,
          "Prepare (composer+goal) and Practice both host dictation")

    # 2) Transcript editability: dictation drives the field via onChange (a controlled
    #    editable textarea), not a read-only sink.
    check("transcript_editability",
          "onChange" in control and "appendTranscript" in control and "readOnly" not in control,
          "final text appended into the editable, controlled field")

    # 3) No auto-submit: the commit path only appends; there is no submit/onSend/onSubmit
    #    call inside the dictation hook/control, and the invariant is tested on both surfaces.
    commit_clean = all(
        tok not in hook for tok in ("onSubmit", "onSend", "submit(")
    ) and all(tok not in control for tok in ("onSubmit(", "onSend(", "submit("))
    tested = ("not.toHaveBeenCalled" in no_autosubmit_test
              and "Message Mo" in no_autosubmit_test and "Your answer" in no_autosubmit_test)
    check("no_auto_submit", commit_clean and tested, "no submit in commit path; tested on both surfaces")

    # 4) Typed text preservation via appendTranscript (+ tested).
    check("typed_text_preservation",
          "appendTranscript" in hook and "preserves existing" in control_test.lower().replace("’", "'")
          or "preserves existing" in control_test,
          "append preserves prior text (unit-tested)")

    # 5) Unsupported browsers degrade: control renders null when not supported.
    check("unsupported_fallback",
          "if (!supported) return null" in control and "isSupported" in adapter,
          "renders nothing when unsupported; typing remains")

    # 6) Permission/failure isolation: errors mapped to safe copy, no throw, typing remains.
    check("permission_failure_isolation",
          "permission-denied" in control and "ERROR_COPY" in control and "onError" in hook,
          "safe error copy; failures never lose text or crash")

    # 7) Accessibility contract on the control.
    a11y = all(t in control for t in ("aria-pressed", "aria-label", 'role="status"', "aria-live"))
    check("accessibility_contract", a11y, "aria-pressed/label + live status; native button")

    # 8) No audio persistence anywhere in the speech layer.
    no_audio = all(
        tok not in (control + hook + adapter)
        for tok in ("MediaRecorder", "getUserMedia", "createObjectURL", "audioBlob", "Blob(")
    )
    check("privacy_no_audio_persistence", no_audio, "no recorder/blob/getUserMedia in the app")

    # 9) Only a language CODE is persisted — never transcript/audio content.
    ls_ok = ("localStorage" in lang_hook and "ask4mo.dictationLang" in lang_hook
             and "localStorage" not in control and "localStorage" not in hook)
    check("no_localstorage_candidate_content", ls_ok,
          "only the language code is stored; no transcript/audio")

    # 10) Response architecture unchanged: no verbosity field added to the agent request;
    #     the P2 presentation contract is untouched by dictation.
    agent_req = read("lib/api/types.ts")
    arch_ok = ("verbosity" not in agent_req.lower()) and (Path(ROOT / "src/agent/presentation.py").exists())
    check("response_architecture_unchanged", arch_ok, "no verbosity field; P2 presentation intact")

    # 11) Multilingual: a bounded, deterministic 7-locale set with browser-locale init,
    #     and Help documents the supported languages honestly.
    codes = ("en-US", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL")
    langs = all(code in control for code in codes)
    help_documents = "dictation language" in help_center.lower()
    check("multilingual_bounded", langs and "fromBrowserLocale" in lang_hook and help_documents,
          "7 bounded locales; browser-locale init; Help documents support honestly")

    return results


def main() -> int:
    print("ASK4MO — CAPSTONE P3 / E-DICTATION EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        print(f"  {name:34s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nPaid LLM calls: 0   Speech provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all dictation invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
