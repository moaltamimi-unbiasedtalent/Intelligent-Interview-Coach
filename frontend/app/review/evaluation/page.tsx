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
        title="Evaluation views connect in a later phase"
        description="The backend exposes read-only evaluation status (no paid runs). The Next.js integration lands after the Career migration. RAGAS never runs from a page load."
      />
    </section>
  );
}
