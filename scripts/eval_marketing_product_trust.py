#!/usr/bin/env python
"""Capstone P10B Wave 7 - Marketing / Product / Trust / Pricing evaluation.

Deterministic, offline invariant checks (no browser, no paid/live provider). Scans the public
marketing surfaces + i18n + pricing + SEO to assert the Wave 7 contract: an Opportunity-centred
story, disciplined claims (market only what exists), truthful pricing (no billing), provider claim
discipline (no Glassdoor/Kununu/Google/LinkedIn integration claim), no fabricated social proof, no
AI-template hype, i18n parity, no emoji/em-dash in customer copy, and SEO/public-private boundaries.
Exits non-zero on any failure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"


def read(rel: str) -> str:
    p = FE / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


LOCALES = ["en", "de", "fr", "es", "it", "pt", "nl", "ru"]


def locale_source(loc: str) -> str:
    """All source text making up one locale's base catalogue (Russian is composed from parts, W9.7)."""
    if loc == "ru":
        return "".join(read(f"lib/i18n/messages/{f}") for f in
                       ("ru.ts", "ru-parts/a.ts", "ru-parts/b.ts", "ru-parts/c.ts"))
    return read(f"lib/i18n/messages/{loc}.ts")


def legal_en_trust() -> str:
    """English `trust` namespace of the W9.6 legal fragment. The Trust page copy moved out of
    TrustContent.tsx into this catalogue block in W9.6, so the trust-claim checks must read it here."""
    legal = read("lib/i18n/messages/w96/legal.ts")
    en_block = legal.split("const en = {", 1)[-1].split("export type LegalFragment", 1)[0]
    return en_block.split("  trust: {", 1)[-1].split("\n  },", 1)[0] if "  trust: {" in en_block else ""
MARKETING_COMPONENTS = [
    "components/marketing/MarketingHome.tsx",
    "components/marketing/ProductContent.tsx",
    "components/marketing/TrustContent.tsx",
    "components/marketing/PricingContent.tsx",
    "components/marketing/MarketingShell.tsx",
]


_CONTRAST = re.compile(r"\b(not as|rather than|instead of|unlike|not just|not a)\b", re.I)
_FORBIDDEN_FRONTEND_BILLING = re.compile(r"@stripe/stripe-js|\bloadStripe\b|js\.stripe\.com|\bcc-number\b|autocomplete=[\"']cc-|\bcard[- ]number\b|\bcreateCheckout\b|name=[\"']card", re.I)


def why_section_contrasts_with_one_off_preparation(en_src: str) -> bool:
    """The positioning must contrast the per-job system with disconnected, one-off or generic preparation (any wording), inside the 'why' block (title through why4)."""
    block = en_src.split("whyTitle", 1)[-1].split("why5Title", 1)[0][:1600]
    return bool(_CONTRAST.search(block)) and bool(re.search(r"\b(one-off|disconnected|generic)\b", block, re.I))


def premium_is_not_purchasable(pricing_ts: str) -> bool:
    """Premium declares no purchase path: ctaKind 'unavailable', purchasable false, no checkout href, and billing disabled (code constant)."""
    m = re.search(r"id:\s*\"premium\".*?\n\s*\},\n", pricing_ts, re.S)
    block = m.group(0) if m else pricing_ts
    return ('ctaKind: "unavailable"' in block and "purchasable: false" in block and "ctaHref: null" in block
            and "BILLING_ENABLED = false" in pricing_ts and "checkout" not in block.lower())


def frontend_billing_violations(files: dict[str, str]) -> list[str]:
    """No candidate-facing payment collection in the frontend: no Stripe SDK or script, no card-number field, no client-side checkout creation. Mentions of the provider
    name in Admin labels and the trusted-redirect allow-list are not payment code; a redirect to a provider-hosted page needs the allow-list module."""
    return sorted(name for name, text in files.items() if _FORBIDDEN_FRONTEND_BILLING.search(text))


# 06A (REQ-LANG-13, LG-13): no page or document may call a language production-qualified, natively reviewed or "multilingual ready"
# while its gates are unpassed. A line may only mention such a phrase inside an explicit negation, condition or requirement.
_LANG_CLAIM = re.compile(
    r"production[- ]qualified|fully[- ]qualified|natively[- ]reviewed|native[- ]reviewed|multilingual[- ]ready|"
    r"all (?:seven|7|eight|8) (?:languages|locales) (?:are |is )?(?:fully )?(?:supported|qualified|ready|production)|"
    r"(?:is|are) qualified for (?:production|real users)", re.I)
_LANG_NEGATION = re.compile(
    r"\b(not|no|never|until|unless|only|before|without|must|cannot|neither|pending|required|requires|require|if|when|whether|"
    r"gate|gates|criteria|means|each|per language|may not|do not|does not|none|nothing|forbid|prevent|disallow|reject|fail|"
    r"claim discipline|no aggregate)\b", re.I)


def language_qualification_claims(text: str) -> list[str]:
    """Lines that assert a language qualification without a negation or condition on the same line (empty = clean)."""
    return [ln.strip()[:160] for ln in text.splitlines() if _LANG_CLAIM.search(ln) and not _LANG_NEGATION.search(ln)]


def run() -> dict[str, tuple[bool, str]]:
    results: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = (bool(ok), detail)

    en = read("lib/i18n/messages/en.ts")
    en_marketing = en.split("marketing: {", 1)[-1].split("\n  },", 1)[0] if "marketing: {" in en else ""
    home = read("components/marketing/MarketingHome.tsx")
    product = read("components/marketing/ProductContent.tsx")
    trust = read("components/marketing/TrustContent.tsx") + "\n" + legal_en_trust()
    shell = read("components/marketing/MarketingShell.tsx")
    pricing_ts = read("lib/pricing.ts")
    robots = read("app/robots.ts")
    sitemap = read("app/sitemap.ts")
    layout = read("app/layout.tsx")
    page = read("app/page.tsx")
    marketing_copy = "\n".join([en_marketing, home, product, trust, shell])
    marketing_copy_l = marketing_copy.lower()

    # --- POSITIONING (Opportunity-centred) ---
    check("home_opportunity_centred",
          "opportunity" in en.split("heroSubtitle", 1)[-1][:400].lower()
          and "featureOpportunityTitle" in en,
          "the hero + a feature lead with the Opportunity (Wave 6)")
    check("company_intelligence_in_story",
          "featureCompanyTitle" in en and "featureCompanyBody" in en,
          "Company Intelligence (Wave 5) is part of the public story")
    check("journey_six_steps",
          all(f"howStep{i}Title" in en for i in range(1, 7)) and "howLead" in en,
          "the how-it-works is a 6-step Opportunity journey")
    check("system_framing",
          "systemTitle" in en and "systemLead" in en,
          "product is framed as one connected system per job")
    check("why_differentiation",
          "whyTitle" in en and all(f"why{i}Title" in en for i in range(1, 5)),
          "a grounded differentiation section exists")
    check("home_uses_no_generic_only_framing",
          why_section_contrasts_with_one_off_preparation(en),
          "positioning explicitly contrasts the per-job system with one-off, disconnected or generic preparation")

    # --- PROVIDER CLAIM DISCIPLINE ---
    for prov in ("glassdoor", "kununu"):
        # These may only appear as an explicit NOT-integrated statement (Trust), never as a source claim.
        appearances = [c for c in MARKETING_COMPONENTS if prov in read(c).lower()]
        ok = all("not integrated" in read(c).lower() for c in appearances)
        check(f"no_{prov}_integration_claim", ok,
              f"{prov} is never claimed as integrated (only 'not integrated' if mentioned)")
    check("no_review_aggregation_claim",
          "aggregate" not in marketing_copy_l and "aggregates reviews" not in marketing_copy_l,
          "no claim of aggregating employee reviews")
    check("no_unrestricted_browsing_claim",
          "browse the web" not in marketing_copy_l and "scrape" not in marketing_copy_l
          and "real-time company" not in marketing_copy_l and "realtime company" not in marketing_copy_l,
          "no unrestricted-browsing or real-time-company-intelligence claim")

    # --- NO FABRICATED SOCIAL PROOF ---
    social = ["testimonial", "trusted by", "customers love", "join thousands", "5-star", "five star",
              "rated 5", "as seen on", "million users", "users worldwide"]
    hits = [s for s in social if s in marketing_copy_l]
    check("no_fabricated_social_proof", not hits, f"no testimonials/counts/ratings ({hits or 'none'})")

    # --- NO UNSUPPORTED ABSOLUTES / HYPE ---
    absolutes = ["100%", "guaranteed", "guarantee you", "bias-free", "bias free", "hallucination-free",
                 "gdpr compliant", "gdpr certified", "fully compliant", "fully secure", "completely secure"]
    ahits = [a for a in absolutes if a in marketing_copy_l]
    check("no_unsupported_absolutes", not ahits, f"no unsupported absolutes ({ahits or 'none'})")
    hype = ["supercharge", "revolutionise", "revolutionize", "game-changing", "game changing",
            "unlock your potential", "next-level", "cutting-edge ai", "powered by cutting"]
    hhits = [h for h in hype if h in marketing_copy_l]
    check("no_ai_template_hype", not hhits, f"no AI-template hype ({hhits or 'none'})")

    # --- PRICING (truthful, no billing) ---
    check("pricing_basic_free",
          '"€0"' in pricing_ts and 'ctaKind: "register"' in pricing_ts,
          "Basic is a real free plan (register)")
    check("pricing_premium_preview",
          premium_is_not_purchasable(pricing_ts),
          "Premium is not purchasable (no purchase path, unapproved preview only); billing is disabled")
    check("premium_claim_softened",
          "higher usage" not in en.lower(),
          "the unenforced 'higher usage' Premium claim is removed")
    # No billing/checkout code in the frontend.
    fe_files: dict[str, str] = {}
    for pth in FE.rglob("*.ts*"):
        sp = str(pth)
        # Skip deps, build output and TEST files (specs legitimately reference card/checkout tokens only to assert their ABSENCE).
        if "node_modules" in sp or "/.next/" in sp or ".spec.ts" in sp or ".test.ts" in sp:
            continue
        fe_files[pth.name] = pth.read_text(encoding="utf-8", errors="ignore")
    billing_hits = frontend_billing_violations(fe_files)
    check("no_billing_code", not billing_hits, f"no candidate payment collection in the frontend ({billing_hits or 'none'})")

    # --- TRUST ---
    tl = trust.lower()
    check("trust_ai_not_facts", "not facts" in tl or "not presented as verified facts" in tl,
          "Trust states AI suggestions are not facts")
    check("trust_opportunity_private", "opportunity is private" in tl,
          "Trust states an Opportunity is private")
    check("trust_sources_separate",
          "not integrated" in tl and ("facts stay separate" in tl or "clearly separate" in tl),
          "Trust separates company facts from opinion and states reviews not integrated")
    check("trust_language_independence",
          "target job market" in tl or "your market" in tl,
          "Trust states language is independent from the target job market")
    check("trust_no_absolutes",
          not any(a in tl for a in ("100%", "certified", "guarantee")),
          "Trust makes no absolute/certification claims")

    # --- OPPORTUNITY vs WORKSPACE ---
    check("opportunity_workspace_distinct",
          "separate from" in en_marketing.lower() and "collaboration" in en_marketing.lower(),
          "public copy distinguishes private Opportunity from collaboration workspace")

    # --- I18N ---
    new_keys = ["featureOpportunityTitle", "featureCompanyTitle", "systemTitle", "whyTitle",
                "howStep6Title", "homePricingTitle"]
    parity = {loc: all(k in locale_source(loc) for k in new_keys) for loc in LOCALES}
    check("i18n_marketing_parity", all(parity.values()),
          "new marketing keys exist in all 8 locales: "
          + (",".join(l for l, v in parity.items() if not v) or "all present"))
    emdash_files = [c for c in MARKETING_COMPONENTS if "—" in read(c)] + \
                   [f"lib/i18n/messages/{l}.ts" for l in LOCALES if "—" in locale_source(l)]
    check("no_emdash_marketing", not emdash_files, f"no em dash in marketing copy ({emdash_files or 'none'})")

    # --- NO EMOJI / CANONICAL BRAND ---
    emoji = re.compile("[\U0001F000-\U0001FAFF☀-⛿✀-➿]")
    emoji_files = [c for c in MARKETING_COMPONENTS if emoji.search(read(c))]
    check("no_emoji_marketing", not emoji_files, f"no emoji iconography in marketing ({emoji_files or 'none'})")
    check("canonical_logo_only",
          "Logo" in shell and "ask4mo-mark.svg" not in shell.replace("Logo", ""),
          "marketing uses the canonical Logo component (no invented/emoji brand)")

    # --- SEO ---
    check("robots_disallows_private",
          all(f'"{p}"' in robots for p in ("/app", "/opportunities", "/company", "/admin")),
          "robots disallows authenticated routes incl. /opportunities and /company")
    check("sitemap_marketing_only",
          not any(p in sitemap for p in ("/app", "/opportunities", "/company", "/admin", "/settings")),
          "sitemap lists marketing routes only")
    check("metadata_no_emdash", "—" not in layout and "—" not in page,
          "root + home metadata contain no em dash")
    check("structured_data_no_ratings",
          "application/ld+json" in page
          and not any(w in page.lower() for w in ("aggregaterating", "ratingvalue", "reviewcount")),
          "Organization JSON-LD present with no fabricated ratings")
    check("icons_from_canonical_mark",
          "ask4mo-mark.svg" in layout and "icons" in layout,
          "favicon/app icons derive from the canonical mark")

    claim_files = {rel: read(rel) for rel in MARKETING_COMPONENTS + ["lib/pricing.ts"]}
    claim_files.update({f"messages/{loc}": locale_source(loc) for loc in LOCALES})
    claim_files["messages/w96/legal.ts"] = read("lib/i18n/messages/w96/legal.ts")
    offenders = {k: language_qualification_claims(v) for k, v in claim_files.items()}
    check("no_language_qualification_claim", not any(offenders.values()),
          "no public page or catalogue calls a language production-qualified before its gates pass (LG-13)")

    return results


SAFETY = {
    "no_language_qualification_claim",
    "no_glassdoor_integration_claim", "no_kununu_integration_claim", "no_review_aggregation_claim",
    "no_unrestricted_browsing_claim", "no_fabricated_social_proof", "no_unsupported_absolutes",
    "no_billing_code", "premium_claim_softened", "trust_ai_not_facts", "opportunity_workspace_distinct",
    "no_emdash_marketing", "no_emoji_marketing", "robots_disallows_private", "structured_data_no_ratings",
}


def main() -> int:
    print("ASK4MO - CAPSTONE P10B WAVE 7 MARKETING / PRODUCT / TRUST / PRICING EVALUATION\n")
    results = run()
    failed = False
    for name in sorted(results):
        ok, detail = results[name]
        if not ok:
            failed = True
        tag = "  <- SAFETY" if (name in SAFETY and not ok) else ""
        print(f"  {name:34s} {'PASS' if ok else 'FAIL'}  {detail}{tag}")
    print(f"\nInvariants: {len(results)}   Paid LLM calls: 0   Paid provider calls: 0   Live calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS (all marketing/product/trust/pricing invariants hold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
