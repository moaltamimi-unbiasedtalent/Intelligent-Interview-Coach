import type { Metadata } from "next";

import { MarketingHome } from "@/components/marketing/MarketingHome";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://ask4mo.example.com";

export const metadata: Metadata = {
  // Opportunity-centred; no em dash in customer-facing copy (P10B Wave 7).
  title: "Ask4Mo - Intelligent Interview Coach",
  description:
    "Prepare for a specific job in one Opportunity: the role, company research, your evidence, coaching with Mo and realistic practice. Private by default, in eight languages. Free to start.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "Ask4Mo - Intelligent Interview Coach",
    description:
      "Everything for one job in a single Opportunity: company research, your evidence, coaching and realistic practice. Free to start.",
    type: "website",
  },
};

// Truthful Organization structured data - name/url/description/logo only. No ratings, reviews or
// aggregate counts are claimed (none exist). Derived from the canonical Ask4Mo identity.
const ORG_JSONLD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Ask4Mo",
  url: SITE,
  description:
    "Ask4Mo is an interview-preparation workspace that brings the role, company research, your evidence, coaching and realistic practice together for one job.",
  logo: `${SITE}/brand/ask4mo-mark.svg`,
};

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        // Static, developer-authored JSON (no user input) - safe to inline.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSONLD) }}
      />
      <MarketingHome />
    </>
  );
}
