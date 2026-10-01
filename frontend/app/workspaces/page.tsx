import type { Metadata } from "next";
import { WorkspacesPanel } from "@/components/workspaces/WorkspacesPanel";

// Metadata title left as-is (static metadata in a server component cannot use t()); localizing
// the metadata title is handled centrally. The visible page header (eyebrow/title/description) is
// localized inside WorkspacesPanel, which renders it via useT().
export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return <WorkspacesPanel />;
}
