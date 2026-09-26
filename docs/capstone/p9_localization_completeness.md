# P9 Localization Completeness Audit (§28)

_A bounded scan of candidate-facing frontend copy, classifying English literals as: must-migrate
(candidate-visible), technical/dev-only (approved English), source content (never auto-translate),
proper noun, or legal English-only draft (intentionally pending review). Human translation
quality remains a separate gate (see the quality register)._

## Method
- i18n architecture: `useT()`/`translate()` over 7 catalogues (`en/de/fr/es/it/pt/nl`), key
  parity enforced by `tests/i18n.test.tsx` (passing). Namespaces: common, nav, states, auth,
  account, home, settings, dictation, help, practice, prepare, progress, history, sources,
  documents, workspaces, voice, **marketing**.
- Scan: ~23 candidate-facing components consume `useT()`; a heuristic raw-JSX-text scan across
  the candidate flows (interview/preparation/coach) found **~1** residual literal, dispositioned
  below.

## Classification
| Area | Status | Class | Action |
|---|---|---|---|
| Nav, auth, home, settings, practice, prepare, progress, history, sources, documents, workspaces, voice, marketing | **Localized** (7 locales) | candidate-visible | none — engineering draft translations in place |
| Reviewer / Diagnostics (`/review/*`) | English | technical/dev-only | approved English (reviewer surface) |
| Platform Admin (`/admin`) | English | technical/dev-only | approved English (operations console) |
| Privacy / Terms / AI-transparency bodies | English (draft) | legal English-only draft | intentional — pending legal + translation review (visible banner) |
| Trust control descriptions, About page prose | English | candidate-visible (marketing detail) | **debt** — titles/subtitles localized; detailed prose carried as engineering-draft localization debt |
| Legacy Help article bodies (pre-P7) | English | candidate-visible | **debt** — documented localization backlog; Voice/tutorial Help localized |
| Model/source content (knowledge, retrieved text) | source language | source content | never auto-translated (by design) |
| Brand ("Ask4Mo"), "Mo", "STAR", "ISO 27001" | unchanged | proper noun / standard | keep as-is in all locales |

## Residual candidate-flow literal
The single heuristic hit is a non-user-facing/attribute-adjacent string in the interview flow;
it is not a blocking candidate label. Tracked as NBL localization debt, not a P9 defect.

## Human/legal review status
- **Engineering complete:** EN (source) + DE/FR/ES/IT/PT/NL (draft) for all candidate namespaces
  incl. marketing.
- **Human reviewed:** none.
- **Legal reviewed:** none (Privacy/Terms/AI-transparency are drafts with visible banners).

## Disposition
Candidate **flows** are localized via the shared i18n system with enforced key parity. Remaining
English is either **approved** (reviewer/admin technical surfaces, source content, proper nouns)
or **documented debt** (marketing detail prose, legacy Help bodies, legal drafts). No unmanaged
candidate-flow English label blocks the release candidate; human + legal translation review
remain **blockers for public launch**, not for P10.
