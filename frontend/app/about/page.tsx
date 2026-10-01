import type { Metadata } from "next";

import { AboutContent } from "@/components/marketing/AboutContent";

// NOTE (P10B-W9.6): page `metadata` (title/description) is intentionally left in English here.
// Metadata localization is handled separately in the W9 localization track. The visible page body
// is localized in the AboutContent client component via useT().
export const metadata: Metadata = {
  title: "About",
  description:
    "About Ask4Mo - an intelligent interview coach built to be trustworthy: grounded, private by default, and honest about its limitations.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return <AboutContent />;
}
