import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { WorkspacesPanel } from "@/components/workspaces/WorkspacesPanel";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Teams & sharing"
        title="Workspaces"
        description="Collaborate by explicitly sharing selected items. Your personal data stays private by default."
      />
      <WorkspacesPanel />
    </section>
  );
}
