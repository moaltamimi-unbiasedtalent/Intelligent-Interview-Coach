import type { Metadata } from "next";

import { TrustContent } from "@/components/marketing/TrustContent";

export const metadata: Metadata = {
  title: "Trust & safety",
  description:
    "The engineering controls behind Ask4Mo: private by default, explicit sharing, sources you can check, human approvals, no voice-trait inference, no audio storage, export and delete.",
  alternates: { canonical: "/trust" },
};

export default function TrustPage() {
  return <TrustContent />;
}
