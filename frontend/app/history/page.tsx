import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/States";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Your sessions"
        title="History"
        description="Completed interview sessions and their reports."
      />
      <EmptyState
        title="Completed interview sessions will appear here"
        description="Finish a practice interview to see its report. History connects to your account in a later phase."
      />
    </section>
  );
}
