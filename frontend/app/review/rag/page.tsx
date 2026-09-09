import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/States";

export const metadata: Metadata = { title: "RAG Inspector" };

export default function RagInspectorPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="RAG Inspector"
        description="Retrieval lanes, evidence and citations behind an answer."
      />
      <EmptyState
        title="RAG diagnostics live in the existing review tools"
        description="Career retrieval is fully implemented and its safe source/citation activity is visible through the Agent Inspector. The dedicated Next.js RAG Inspector has not been migrated; the legacy Streamlit diagnostic remains available for deeper retrieval inspection."
      />
    </section>
  );
}
