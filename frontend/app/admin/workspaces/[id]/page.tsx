import { PageHeader } from "@/components/layout/PageHeader";
import { WorkspaceDetailView } from "@/components/admin/WorkspaceDetailView";

export default async function AdminWorkspaceDetailViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Workspace" description="Workspace metadata and members. Shared items are never listed." />
      <WorkspaceDetailView workspaceId={Number(id)} />
    </section>
  );
}
