import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { RagDiagnosticsClient } from "@/components/review/RagDiagnosticsClient";

export const metadata: Metadata = { title: "Knowledge & RAG" };

export default function RagInspectorPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Knowledge & RAG"
        description="Governed knowledge runtime and offline retrieval-quality evaluation (read-only)."
      />
      <RagDiagnosticsClient />
    </section>
  );
}
