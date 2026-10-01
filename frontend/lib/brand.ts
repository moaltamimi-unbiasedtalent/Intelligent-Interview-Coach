/**
 * Protected brand invariants (P10B-W9.7).
 *
 * `BRAND_SLOGAN` is the Ask4Mo slogan and is NEVER translated, transliterated or re-punctuated in any
 * interface language (current or future). Every locale resolves `common.tagline` to exactly this
 * value; copy that embeds the slogan embeds it verbatim. It is defined ONCE here, and the
 * hardcoded-English guard (`scripts/scan-i18n.mjs`) treats ONLY this exact phrase as an approved brand
 * invariant (not arbitrary English marketing copy). Enforced by `tests/brand-slogan-invariant.test.ts`.
 */
export const BRAND_SLOGAN = "Ask More. Be More.";
