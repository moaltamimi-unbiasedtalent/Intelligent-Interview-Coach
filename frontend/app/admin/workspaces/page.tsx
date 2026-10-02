import { PageHeader } from "@/components/layout/PageHeader";
import { WorkspacesView } from "@/components/admin/WorkspacesView";

export default function AdminWorkspacesViewPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Workspaces" description="Workspace metadata only. Shared content is never shown." />
      <WorkspacesView />
    </section>
  );
}
