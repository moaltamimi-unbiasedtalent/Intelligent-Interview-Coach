import type { Metadata } from "next";

import { PricingContent } from "@/components/marketing/PricingContent";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Ask4Mo plans: start free with Basic. Premium subscriptions are planned and not available yet. Privacy and data rights are always included.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return <PricingContent />;
}
