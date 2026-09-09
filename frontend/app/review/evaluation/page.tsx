import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Evaluation" };

export default function EvaluationPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Evaluation"
        description="Deterministic retrieval metrics and the optional RAGAS generation-quality layer (read-only)."
      />
      <EmptyState
        title="Evaluation is run through the project evaluation tools"
        description="Deterministic Agent evaluation, the live-model harness and optional RAGAS evaluation are available through the repository scripts and evidence artifacts. Paid evaluation never runs from this page."
      />
    </section>
  );
}
