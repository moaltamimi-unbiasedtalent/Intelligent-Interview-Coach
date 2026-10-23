# Language review packs (06F) and independent evaluation (06G)

**Status: MATERIALS ONLY. No reviewer is appointed, no review has happened, no sign-off is recorded.** Everything here is prepared so that work starts the day the owner appoints people (OD-LANG-03, OD-LANG-04) and approves a budget (OD-BUDGET). Nothing here qualifies a language.

| What | Where |
|---|---|
| Per-language review pack (en, de, fr, es, it, pt, nl): instructions, interface strings by surface, Mo sentences, interview samples, legal pointers, blank sign-off form | `<code>/` (generated) |
| Freeze manifest with per-language digests (NOT FROZEN: no freeze SHA named) | `FREEZE_MANIFEST.json` (generated) |
| What the owner must supply and how each item maps to `language_readiness.json` | `OWNER_READINESS_CHECKLIST.md` |
| Evaluation protocol, sample-size guidance, pilot revalidation checklist | `docs/production/execution/evidence/06G_HUMAN_EVAL_PROTOCOL.md`, `06G_SAMPLE_SIZE_GUIDANCE.md`, `06G_PILOT_REVALIDATION_CHECKLIST.md` |

Commands (offline, no model call):

```
python scripts/language_review_pack.py --write      # regenerate the packs and the manifest
python scripts/language_review_pack.py --check      # fail when the committed packs are stale
python scripts/language_review_pack.py --freeze --release-sha SHA --out DIR        # owner names the SHA
python scripts/language_review_pack.py --diff --baseline DIR/FREEZE_SNAPSHOT.json --language de --out DIR2
python scripts/language_review_pack.py --validate-form COMPLETED.json --gate LG-11  # reports gaps; records nothing
python scripts/language_human_eval.py selftest        # 06G protocol end to end on fake data
```

The packs are generated from the interface catalogue (`frontend/lib/i18n/messages`, read with node), the 06C policy sentence inventory, the email templates and the synthetic prompt bank. When a catalogue key changes, regenerate with `--write` (a test fails while the committed packs are stale), exactly as for `06A_LOCALE_AUDIT.md`.

The legal review pack of 05E (`docs/production/legal_review/`) is referenced conditionally: if it exists in the release tree the legal qualifier reviews its documents as well; nothing here depends on it.

This work extends the 06C blinded rating protocol and harness (`06C_RATING_PROTOCOL.md`, `src/language_quality/rating.py`). The 06C branch is stacked below this one and merges first.
