import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EvaluationClient } from "@/components/review/EvaluationClient";
import { RequirePlatformAdmin } from "@/components/auth/RequirePlatformAdmin";

export const metadata: Metadata = { title: "Evaluation", robots: { index: false, follow: false } };

// P10B-W9.3: internal evaluation diagnostics — platform-admin-only.
export default function EvaluationPage() {
  return (
    <RequirePlatformAdmin>
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Evaluation"
        description="Deterministic retrieval metrics and the optional RAGAS generation-quality layer (read-only, offline)."
      />
      <EvaluationClient />
    </section>
    </RequirePlatformAdmin>
  );
}
