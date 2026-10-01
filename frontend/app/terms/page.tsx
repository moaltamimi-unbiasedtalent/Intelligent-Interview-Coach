import type { Metadata } from "next";

import { TermsContent } from "@/components/marketing/TermsContent";

// NOTE (P10B-W9.6): page `metadata` (title/description) is intentionally left in English here.
// Metadata localization is handled separately in the W9 localization track. The visible page body
// is localized in the TermsContent client component via useT().
export const metadata: Metadata = {
  title: "Terms of use",
  description:
    "Terms for using Ask4Mo. AI preparation guidance is not professional, legal or employment advice. Engineering draft - pending legal review.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return <TermsContent />;
}
