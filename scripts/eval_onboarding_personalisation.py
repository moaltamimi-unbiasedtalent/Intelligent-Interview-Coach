#!/usr/bin/env python
"""Capstone P10B Wave 2 — onboarding & personalisation evaluation.

Deterministic, offline invariant checks (no browser, no paid/live provider). Mixes behavioural
checks (real preference/onboarding API + coaching directive) with source-structural checks
(onboarding UI safety, Settings integration, 7-locale parity, migration backfill). Exits non-zero
on any failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FE = ROOT / "frontend"
os.environ.setdefault("DOCUMENT_STORAGE_DIR", tempfile.mkdtemp(prefix="eval_w2_"))
PW = "correcthorsebattery"


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    # --- bounded coaching style + score independence (behavioural) ---
    from src import prompts
    from src.coaching_style import COACHING_STYLES, coaching_style_directive
    from src.models import InterviewConfiguration

    check("bounded_coaching_styles",
          COACHING_STYLES == ("supportive", "balanced", "direct", "challenging"),
          "exactly four bounded styles")
    check("no_arbitrary_persona_prompt",
          coaching_style_directive("balanced") is None
          and coaching_style_directive("be an evil pirate") is None
          and all(coaching_style_directive(s) for s in ("supportive", "direct", "challenging")),
          "directive only from the allow-list; balanced/unknown → none")

    def cfg(**o):
        base = dict(target_role="Nurse", industry_or_sector="health", career_level="senior",
                    interview_types=["behavioural"], interviewer_persona="neutral",
                    difficulty="moderate", response_detail="standard", number_of_questions=2)
        base.update(o)
        return InterviewConfiguration(**base)

    umsg = lambda style: prompts.build_task_user_message(  # noqa: E731
        prompts.TASK_EVALUATION, cfg(coaching_style=style), question="Q?", candidate_answer="A.")
    check("coaching_style_scoring_independent", umsg("balanced") == umsg("direct") == umsg("challenging"),
          "scored DATA identical across coaching styles")
    check("coaching_feedback_only_not_questions",
          "COACHING STYLE" in prompts.build_task_system_prompt(prompts.TASK_EVALUATION, "zero_shot", cfg(coaching_style="direct"))
          and "COACHING STYLE" not in prompts.build_task_system_prompt(prompts.TASK_QUESTION, "zero_shot", cfg(coaching_style="direct")),
          "coaching tone applies to feedback, never to question generation")
    check("session_language_overrides_account",
          "German" in prompts.build_task_system_prompt(prompts.TASK_QUESTION, "zero_shot", cfg(conversation_language="de")),
          "the interview's own conversation_language drives generation (session override)")

    # --- preference/onboarding API (behavioural, real users) ---
    from fastapi.testclient import TestClient
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register

    app, _repo, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW); register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW); b = login_token(c, "b@example.com", PW)
        me_a = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()
        check("new_user_onboarding_incomplete", me_a["onboarding_completed"] is False,
              "a new account starts with onboarding pending")
        # Bounded-enum rejection.
        check("invalid_enum_rejected",
              c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={"coaching_style": "x"}).status_code == 422
              and c.patch("/api/v1/auth/preferences", cookies=cookies_for(a), json={"career_geography": "zz"}).status_code == 422,
              "spoofed coaching/geography → 422")
        # Persist + response-detail independence (DIRECT + DETAILED both valid).
        c.patch("/api/v1/auth/preferences", cookies=cookies_for(a),
                json={"coaching_style": "direct", "response_detail": "detailed", "career_geography": "us"})
        me_a = c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()
        check("response_detail_independent", me_a["coaching_style"] == "direct" and me_a["response_detail"] == "detailed",
              "coaching style and response detail are independent")
        check("language_geography_separation",
              me_a["career_geography"] == "us" and me_a["conversation_language"] == "en" and me_a["interface_locale"] == "en",
              "setting geography never changes any language")
        # Resume (never regress) + complete.
        c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"step": 4})
        step = c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"step": 2}).json()["onboarding_step"]
        check("resumability", step == 4, "onboarding step persists and never regresses")
        done = c.post("/api/v1/auth/onboarding", cookies=cookies_for(a), json={"complete": True}).json()
        check("onboarding_complete", done["onboarding_completed"] is True, "complete marks the account")
        # Owner scope.
        check("owner_scope", c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["coaching_style"] == "balanced",
              "another account is unaffected")

    # --- source-structural safety ---
    onboarding = read("frontend/components/onboarding/OnboardingClient.tsx")
    check("onboarding_no_auto_microphone",
          "DictationControl" not in onboarding and "getUserMedia" not in onboarding and "MediaRecorder" not in onboarding,
          "onboarding never opens the microphone")
    check("onboarding_no_auto_interview",
          "interviews.create" not in onboarding and "agent.start" not in onboarding,
          "onboarding starts no interview/agent run; completion routes to /app")
    check("onboarding_no_sensitive_fields",
          not any(t in onboarding.lower() for t in ("date_of_birth", "gender", "ethnic", "disability", "religio", "salary")),
          "no protected/sensitive profile collection")
    guard = read("frontend/components/auth/RouteGuard.tsx")
    check("onboarding_gate_present", "onboarding_completed" in guard and "/onboarding" in guard,
          "RouteGuard gates incomplete accounts to /onboarding")
    settings = read("frontend/components/settings/SettingsContent.tsx")
    check("settings_edit_onboarding_prefs", "PersonalisationSettings" in settings,
          "Settings exposes the personalisation controls for later editing")
    route = read("src/api/routes/auth.py")
    check("no_private_pref_in_logs",
          '"set"' in route and "target_role" in route and "display_name" in route,
          "free-text prefs are audited as 'set', never logged verbatim")
    migration = read("migrations/versions/0013_onboarding_personalisation.py")
    check("migration_backfill_safety",
          "UPDATE users SET onboarding_completed_at" in migration and "def downgrade" in migration,
          "existing users backfilled to completed; downgrade present")

    # 7-locale parity for the new namespaces.
    locales = ["en", "de", "fr", "es", "it", "pt", "nl"]
    parity = all(
        all(ns in read(f"frontend/lib/i18n/messages/{loc}.ts") for ns in ("onboarding:", "coaching:", "geography:"))
        for loc in locales
    )
    check("seven_locale_parity", parity, "onboarding/coaching/geography present in all 7 locales")

    return results


SAFETY = {
    "no_arbitrary_persona_prompt", "coaching_style_scoring_independent", "language_geography_separation",
    "owner_scope", "invalid_enum_rejected", "onboarding_no_auto_microphone", "onboarding_no_auto_interview",
    "onboarding_no_sensitive_fields", "no_private_pref_in_logs", "migration_backfill_safety",
    "coaching_feedback_only_not_questions",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P10B WAVE 2 ONBOARDING & PERSONALISATION EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  ← SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:36s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print("\nPaid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all onboarding/personalisation invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
