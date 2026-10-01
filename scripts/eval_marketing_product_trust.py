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
          "generic" in en.split("whyTitle", 1)[-1][:120].lower(),
          "positioning explicitly contrasts with a generic interview generator")

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
          'ctaKind: "request"' in pricing_ts and "BILLING_ENABLED = false" in pricing_ts,
          "Premium is a preview request; billing is disabled")
    check("premium_claim_softened",
          "higher usage" not in en.lower(),
          "the unenforced 'higher usage' Premium claim is removed")
    # No billing/checkout code in the frontend.
    billing_hits = []
    for pth in FE.rglob("*.ts*"):
        s = str(pth)
        # Skip deps, build output and TEST files (specs legitimately reference card/checkout tokens
        # only to assert their ABSENCE - counting them would be a false positive).
        if "node_modules" in s or "/.next/" in s or ".spec.ts" in s or ".test.ts" in s:
            continue
        t = pth.read_text(encoding="utf-8", errors="ignore").lower()
        if re.search(r"\b(stripe|checkout session|createcheckout|card number|cc-number)\b", t):
            billing_hits.append(pth.name)
    check("no_billing_code", not billing_hits, f"no checkout/billing code ({billing_hits or 'none'})")

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

    return results


SAFETY = {
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
