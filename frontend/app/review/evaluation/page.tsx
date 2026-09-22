import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EvaluationClient } from "@/components/review/EvaluationClient";

export const metadata: Metadata = { title: "Evaluation" };

export default function EvaluationPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Evaluation"
        description="Deterministic retrieval metrics and the optional RAGAS generation-quality layer (read-only, offline)."
      />
      <EvaluationClient />
    </section>
  );
}
