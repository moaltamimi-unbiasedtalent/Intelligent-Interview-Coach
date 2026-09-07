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
        title="Retrieval inspection connects in a later phase"
        description="The backend already exposes safe retrieval data; the Next.js integration lands with the Career migration (Phase 3C). The Streamlit RAG Inspector remains available meanwhile."
      />
    </section>
  );
}
