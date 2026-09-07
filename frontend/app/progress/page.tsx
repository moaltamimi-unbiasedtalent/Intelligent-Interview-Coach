import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Progress" };

export default function ProgressPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Your journey"
        title="Progress"
        description="Your preparation trajectory, recurring strengths and priorities across sessions."
      />
      <EmptyState
        title="Your preparation progress will appear here"
        description="As you prepare and practise, we'll show what's improving and what to focus on next. Preparation memory arrives in a later phase."
      />
    </section>
  );
}
