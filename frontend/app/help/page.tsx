import type { Metadata } from "next";

import { HelpPageContent } from "@/components/help/HelpPageContent";

// NOTE (P10B-W9.6): page `metadata` (title) is intentionally left in English here. Metadata
// localization is handled separately in the W9 localization track. The visible page body is
// localized in the HelpPageContent client component via useT().
export const metadata: Metadata = { title: "Help" };

export default function HelpPage() {
  return <HelpPageContent />;
}
