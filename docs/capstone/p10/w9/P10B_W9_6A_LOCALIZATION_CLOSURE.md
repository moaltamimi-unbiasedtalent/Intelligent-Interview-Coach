# P10B-W9.6A — Localization Closure: Help Content + Guard Coverage

Closure patch for a W9.6 acceptance-gate inconsistency. Frontend localization + a deterministic
scanner fix + an eval read-path fix. **No migration, no API change, no backend locale change, no RC,
no Pilot 2, no P10C, 0 paid/live calls.** Not W9.7 — no Russian.

## 1. Baseline

- From W9.6 `fix/p10b-w9-6-full-localization` @ `847215b` (ancestry intact through W9.1–W9.5). New branch
  `fix/p10b-w9-6a-help-localization-closure`. Alembic head `0014_opportunities` (unchanged). No
  RC-P10-003. RC-P10-002 immutable.

## 2. Discrepancy

The W9.6 report simultaneously claimed "every Ask4Mo-owned candidate-facing string switches with the
interface language" and the scanner reported **0 offenders**, while also listing "HelpCenter article
bodies" as a deferred English backlog. Both could not be true: either Help was localized (and the
limitation was stale), or Help was still English **and the new guard was not detecting it**.

Factual finding: Help was still English, and the guard did not detect it.

## 3. Root cause

The Help Center content lived in a TS object/array literal in
`components/help/HelpCenter.tsx`:

```ts
const SECTIONS: Section[] = [
  { id: "getting-started", title: "Getting started", articles: [
    { q: "What is Ask4Mo?", a: "An AI interview coach. ..." }, ... ] }, ...
];
```

The W9.6 scanner (`scripts/scan-i18n.mjs`) inspected only **(a)** JSX text nodes and **(b)** JSX
attribute literals (`placeholder=`/`aria-label=`/...). Candidate copy stored as **object-literal
property values** (`title:` / `q:` / `a:`) is neither, so all of it was invisible to the guard — hence
a false "0 offenders". (The P7/P7.5 Voice section was already catalogue-driven via `t("voice.*")`.)

Factual Help inventory: **12 hardcoded sections, 66 articles → 144 candidate-facing strings** (12
section titles + 66 question/answer pairs). Per section: getting-started 4, prepare 6, practice 4,
progress 2, history 4, sources 5, dictation 8, documents 13, memory 3, privacy 4, troubleshooting 8,
reviewer 5.

## 4. Help localization

- Extracted the 144 English strings into a typed catalogue source of record
  `lib/i18n/messages/w96/help/en.ts` (verbatim — English wording unchanged), with stable keys
  (`<sectionPrefix>Title`, `<sectionPrefix><n>q`, `<sectionPrefix><n>a`).
- Six locale files `lib/i18n/messages/w96/help/{de,fr,es,it,pt,nl}.ts`, each **144 keys** (engineering
  localization, no em dash, product terms consistent with the existing catalogues; `Ask4Mo`/`Mo`,
  `CV`/`JD`/`OCR`, file formats, model tiers, `Glassdoor`/`Kununu`, feature proper nouns kept verbatim).
- `lib/i18n/messages/w96/help/index.ts` assembles them into the standard W9.6 fragment shape
  (`{ locale: { help: {...} } }`) with **compile-time parity** (each non-English map typed as the
  English key set → a missing key fails `tsc`; extras are caught by `tests/i18n.test.tsx`). It is added
  as a sixth fragment in `lib/i18n/messages/w96/index.ts`, so it deep-merges into the `help` namespace
  of every locale catalogue.
- `components/help/HelpCenter.tsx` keeps the section **structure** (ids/order/counts) in code as
  `HELP_SECTIONS` (title/question/answer **keys**) and resolves every string via `t()` at render —
  exactly like the pre-existing Voice section. No article was added or removed; the Help Center was not
  redesigned. Search still filters over the (now localized) rendered content; no search redesign.
- Catalogue total after closure: **527 + 144 = 671 new W9.6/W9.6A keys per locale** across the six
  fragments.

## 5. Guard fix (the blind spot)

Extended `scripts/scan-i18n.mjs` with a third pass **(c)**: candidate-facing CONTENT in object/array
literals — a string literal assigned to a bounded set of content keys (`title`, `subtitle`, `heading`,
`description`, `label`, `hint`, `helper`, `placeholder`, `question`, `answer`, `q`, `a`, `body`,
`message`, `summary`, `intro`, `note`, `cta`, `tooltip`, `caption`, `empty`, `emptyText`, `text`) whose
value reads as English prose. It is deliberately bounded: structural/technical keys (`id`, `code`,
`href`, `className`, `type`, `value`, `slug`, `testId`, …) are **not** in the set, and `looksEnglish`
rejects identifiers / i18n key refs / code tokens, so class names, routes, enum tokens, test ids and
`help.*` key references are not flagged. Two machine-readable, non-candidate-chrome categories are
stripped before scanning (same deferred class as page metadata): `export const metadata` /
`generateMetadata` blocks, and schema.org JSON-LD objects (those carrying `"@context"`).

The scanner's pure detector is now exported (`scanSource`/`looksEnglish`/`stripNoise`), with the CLI
guarded behind an entrypoint check, so a test can exercise it without filesystem side effects.

## 6. Other blind spots found by the improved scanner

Running the improved guard across the candidate frontend surfaced, beyond Help:

- **`components/preparation/PrepareResponsive.tsx`** — a mobile tab `label: "Preparation"`. Localized
  via `t("nav.prepare")` ("Mo" stays as an allowlisted proper noun).
- **`components/ui/DictationControl.tsx`** — the dictation language selector's option labels were a
  hardcoded English array (`label: "English" | "German" | ...`). Replaced with each language's own
  native name (endonym) resolved from the canonical locale registry (`APP_LOCALES.nativeLabel`),
  matching how the interface/conversation selectors render — locale-independent, no hardcoded English,
  and dictation support/codes are unchanged (separation preserved). `LanguageSettings.tsx` uses the
  same helper.
- **Page `metadata` titles** and the home **JSON-LD** `description` are machine-readable crawler data,
  not candidate-rendered chrome — excluded (documented), consistent with W9.6 §5.

No genuine candidate-facing English was moved to the allowlist to keep "0".

## 7. Tests

- `tests/no-hardcoded-english.test.ts` — the guard, now covering object-literal content; **0 offenders**.
- `tests/scan-i18n-guard.test.ts` (NEW, regression) — proves the previously-escaping pattern
  `{ q: "...", a: "..." }` (and `title`/`body`/`description`/`label`/`message`) is now detected, and
  that key refs, structural keys, metadata, JSON-LD and ternary fragments are NOT flagged.
- `tests/i18n.test.tsx` — 7-locale catalogue parity (now includes the 144 Help keys).
- `e2e/help-localization.spec.ts` (NEW) — H1 German Help (heading/section/article title/body/search),
  H2 no English leakage, H3 seven-locale section-heading smoke, H4 replay-tour launcher localized +
  starts, H5 localized search + localized no-result state.
- `scripts/eval_dictation_experience.py` — `multilingual_bounded` now reads the Help dictation
  documentation from its new catalogue location (content moved out of `HelpCenter.tsx`).

## 8. Final status

- Scanner: **0 unexplained candidate-facing offenders**; allowlist = the single reviewer-only
  `components/agent/AgentInspector.tsx` (W9.3 admin-gated), unchanged.
- Gates (0 paid, 0 live): `typecheck` ✓ · `lint` ✓ (0 warnings) · `npm test` **350** (61 files) ·
  `scan-i18n` **0** · `e2e/help-localization` **11** + `e2e/localization` (W9.6) **11** + regression
  (i18n/navigation/settings-memory/welcome-tutorial/dictation/service-resilience/service-recovery/
  review-access/opportunity*) all green · evals `i18n_l10n` (incl. scanner) / `dictation` / `voice` /
  `realtime_voice` / `release_candidate` (27) / `identity` (1.0) **PASS**.
- W9.6 can now truthfully be marked **DELIVERED** (the limitation that blocked it is closed).

## 9. Remaining legitimate limitations

- Legal/privacy/terms/AI-transparency AND these Help translations are **engineering drafts**;
  human/legal review pending (unchanged status).
- Page `metadata` titles remain English (architecture-bound: needs locale-aware `generateMetadata`).
- Minor cross-file terminology divergence for a few feature proper nouns (e.g. `Deep Dive`,
  `Story Bank`): this Help fragment keeps them verbatim as proper nouns, whereas some older catalogue
  prose translates them. Cosmetic; not a gate.

## 10. W9.7 (Russian) insertion points — do NOT action now

- `src/locales.py`: add `"ru"` to `SUPPORTED_LOCALE_CODES` + `AppLocale` (one backend place).
- `frontend/lib/i18n/locales.ts`: add the `ru` entry to `APP_LOCALES`.
- Add `frontend/lib/i18n/messages/ru.ts` (base) + a `ru` block to every `w96/*.ts` fragment, including
  a new `w96/help/ru.ts` (144 keys) wired in `w96/help/index.ts`. Parity is enforced by `tsc` + the
  catalogue test.
- Keep speech (`DICTATION_LANGUAGES`/`ttsLocales`), taxonomy and geography lists separate.
