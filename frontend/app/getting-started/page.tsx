import type { Metadata } from "next";

import { GettingStartedContent } from "@/components/marketing/GettingStartedContent";

export const metadata: Metadata = {
  title: "Getting started",
  description:
    "Start with one job: create an Opportunity, add context and evidence, prepare with Mo, practise out loud, review the feedback and repeat. A short visual path to your first practice.",
  alternates: { canonical: "/getting-started" },
};

export default function GettingStartedPage() {
  return <GettingStartedContent />;
}
