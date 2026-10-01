import type { Metadata } from "next";

import { AiTransparencyContent } from "@/components/marketing/AiTransparencyContent";

// NOTE (P10B-W9.6): page `metadata` (title/description) is intentionally left in English here.
// Metadata localization is handled separately in the W9 localization track. The visible page body
// is localized in the AiTransparencyContent client component via useT().
export const metadata: Metadata = {
  title: "AI transparency",
  description:
    "How Ask4Mo uses AI: when AI vs deterministic logic runs, specialist agents, RAG/evidence, model limits, human approvals, and what Ask4Mo never infers.",
  alternates: { canonical: "/ai-transparency" },
};

export default function AiTransparencyPage() {
  return <AiTransparencyContent />;
}
