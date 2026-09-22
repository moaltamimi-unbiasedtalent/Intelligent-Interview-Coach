import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { HelpCenter } from "@/components/help/HelpCenter";

export const metadata: Metadata = { title: "Help" };

export default function HelpPage() {
  return (
    <section data-tour="help">
      <PageHeader
        eyebrow="How Ask4Mo works"
        title="Help"
        description="A searchable guide to every part of Ask4Mo, the ideas behind it, and a replayable guided tour."
      />
      <HelpCenter />
    </section>
  );
}
