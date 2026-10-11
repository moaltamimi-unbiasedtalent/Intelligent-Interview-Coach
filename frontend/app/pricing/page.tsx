import type { Metadata } from "next";

import { PricingContent } from "@/components/marketing/PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Ask4Mo pricing: start free with Basic or choose Premium for €19.99 per month. Privacy and data rights are always included.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return <PricingContent />;
}
