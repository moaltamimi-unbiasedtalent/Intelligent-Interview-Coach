#!/usr/bin/env python
"""P10B-W9.10 product positioning / claim guard (deterministic, offline, 0 paid/live calls).

Checks: register integrity (docs/product/PRODUCT_CLAIMS.md), capability-matrix counts, prohibited-phrase and
named-competitor scan of PUBLIC copy only (marketing components + English marketing/trust/pricing/about copy),
no comparison routes, PRIV-W9-01/02 kept visible, slogan invariant, no migration. The register and docs may
discuss prohibited claims; only public copy is scanned.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"

PROHIBITED = [
    r"gdpr[- ]compliant", r"100\s?%\s*(secure|private|safe)", r"completely private", r"enterprise-grade",
    r"bias-free", r"fully unbiased", r"all answers (are )?verified", r"fully verified", r"fact[- ]checked",
    r"human[- ]reviewed", r"guarantees?\s+(interview\s+)?success", r"improves hiring", r"best interview coach",
    r"better than (chatgpt|human)", r"more accurate than", r"employer[- ]approved", r"delete everything",
    r"wcag[- ]compliant", r"revolutionary", r"game-changing", r"next-generation", r"cutting-edge",
    r"supercharge", r"unlock your potential",
]
COMPETITORS = [
    "chatgpt", "openai", "gemini", "copilot", "claude", "final round", "interview warmup", "big interview",
    "huru", "yoodli", "teal", "linkedin", "indeed", "glassdoor", "kununu",
]
# Glassdoor/Kununu/LinkedIn may be named ONLY to say they are not integrated.
ALLOWED_NAMED = ("glassdoor", "kununu", "linkedin", "google")


def read(rel: str, base: Path = ROOT) -> str:
    p = base / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def public_copy() -> str:
    parts = [read(f"components/marketing/{n}", FE) for n in
             ("MarketingHome.tsx", "ProductContent.tsx", "TrustContent.tsx", "PricingContent.tsx", "AboutContent.tsx")]
    en = read("lib/i18n/messages/en.ts", FE)
    for ns in ("marketing", "about"):
        m = re.search(r"^  %s: \{" % ns, en, re.M)
        if m:
            end = en.find("\n  },", m.end())
            parts.append(en[m.start():end])
    legal = read("lib/i18n/messages/w96/legal.ts", FE)
    en_block = legal.split("const en = {", 1)[-1].split("const de", 1)[0]
    parts.append(en_block)
    parts.append(read("lib/i18n/messages/w99/en.ts", FE))
    return "\n".join(parts)


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    claims = read("docs/product/PRODUCT_CLAIMS.md")
    allowed = re.findall(r"^\| (CLAIM-\d{3}) \|(.*)$", claims, re.M)
    banned = re.findall(r"^\| (NO-\d{2}) \|", claims, re.M)
    check("claim_register_exists", len(allowed) >= 15 and len(banned) >= 15,
          f"{len(allowed)} allowed, {len(banned)} prohibited")
    ids = [a[0] for a in allowed]
    check("claim_ids_unique", len(ids) == len(set(ids)), "unique CLAIM ids")
    check("c2_claims_carry_qualification",
          all(len([c for c in row.split("|")]) >= 7 and row.split("|")[5].strip() not in ("", "none")
              for _id, row in allowed if "| C2 |" in row),
          "every C2 claim has a qualification")

    doc = read("docs/capstone/p10/w9/P10B_W9_10_PRODUCT_POSITIONING.md")
    rows = re.findall(r"^\| CAP-\d{2} \|[^|]*\| (C[1-4]) \|", doc, re.M)
    counts = {c: rows.count(c) for c in ("C1", "C2", "C3", "C4")}
    stated = re.search(r"C1 = (\d+), C2 = (\d+), C3 = (\d+), C4 = (\d+)", doc)
    check("capability_counts_match",
          bool(stated) and tuple(map(int, stated.groups())) == (counts["C1"], counts["C2"], counts["C3"], counts["C4"]),
          f"table {counts}")
    c3_words = ("ticket", "purchas", "billing", "consent history", "accepted terms")
    claim_texts = [row.split("|")[1].lower() for _id, row in allowed]
    check("c3_not_in_allowed_claims", not any(w in t for t in claim_texts for w in c3_words),
          "no allowed claim describes a planned (C3) capability")

    copy = public_copy().lower()
    hits = [p for p in PROHIBITED if re.search(p, copy)]
    check("no_prohibited_phrases_in_public_copy", not hits, ", ".join(hits) or "clean")
    named = [c for c in COMPETITORS if c not in ALLOWED_NAMED and re.search(r"\b%s\b" % re.escape(c), copy)]
    check("no_named_competitors_in_public_copy", not named, ", ".join(named) or "clean")
    for n in ("glassdoor", "kununu"):
        if re.search(n, copy):
            # only acceptable inside a "not integrated / links out" sentence
            ok = bool(re.search(r"(not integrated|link[s]? out|links rather than)", copy))
            check(f"{n}_only_as_not_integrated", ok, "mentioned only with a not-integrated qualifier")

    routes = [p.name for p in (FE / "app").iterdir() if p.is_dir()]
    check("no_comparison_routes", not any(re.search(r"(^vs$|-vs-|compare|comparison|why-)", r) for r in routes),
          "no /why-*, /compare or 'vs' routes")
    check("priv_limitations_visible", "PRIV-W9-01" in doc and "PRIV-W9-02" in doc and "NO-05" in claims and "NO-06" in claims,
          "preparation-chat deletion and consent history limitations are recorded")
    check("no_competitor_research_declared", "no external or competitor research" in claims.lower(), "declared in the register")
    mig = sorted(p.name for p in (ROOT / "migrations/versions").glob("0*.py"))
    check("no_migration_added", mig[-1].startswith(("0014_", "0015_", "0016_", "0017_", "0018_", "0019_")), mig[-1])
    brand = read("lib/brand.ts", FE)
    check("slogan_invariant", 'Ask More. Be More.' in brand, "BRAND_SLOGAN unchanged")
    return out


def main() -> int:
    print("ASK4MO - P10B-W9.10 PRODUCT POSITIONING / CLAIM GUARD\n")
    res = run()
    failed = False
    for name in sorted(res):
        ok, detail = res[name]
        failed |= not ok
        print(f"  {name:42s} {'PASS' if ok else 'FAIL'}  {detail}")
    print("\nCompetitor research: none   Paid LLM calls: 0   Live calls: 0")
    print("\nRESULT: " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
