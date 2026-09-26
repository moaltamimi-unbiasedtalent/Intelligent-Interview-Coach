import type { Metadata } from "next";

import { MarketingHome } from "@/components/marketing/MarketingHome";

export const metadata: Metadata = {
  title: "Ask4Mo — Intelligent Interview Coach",
  description:
    "Ask4Mo is your intelligent interview coach: grounded preparation, realistic practice and private-by-default evidence, in seven languages. Free to start.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "Ask4Mo — Intelligent Interview Coach",
    description:
      "Grounded preparation, realistic Interview Practice and private-by-default evidence. Free to start.",
    type: "website",
  },
};

export default function HomePage() {
  return <MarketingHome />;
}
