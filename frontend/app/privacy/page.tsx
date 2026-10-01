import type { Metadata } from "next";

import { PrivacyContent } from "@/components/marketing/PrivacyContent";

// NOTE (P10B-W9.6): page `metadata` (title/description) is intentionally left in English here.
// Metadata localization is handled separately in the W9 localization track. The visible page body
// is localized in the PrivacyContent client component via useT().
export const metadata: Metadata = {
  title: "Privacy",
  description:
    "How Ask4Mo handles your data: what is collected, how it is used, retention, export and deletion. Engineering draft - pending legal review.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return <PrivacyContent />;
}
