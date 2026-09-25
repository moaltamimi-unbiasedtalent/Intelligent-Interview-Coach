import type { Metadata } from "next";

import { PricingContent } from "@/components/marketing/PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Ask4Mo pricing: start free with Basic. Premium is a preview — there is no online payment. Privacy and data rights are always free.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return <PricingContent />;
}
