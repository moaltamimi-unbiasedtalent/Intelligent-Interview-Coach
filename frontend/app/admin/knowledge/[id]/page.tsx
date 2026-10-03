import { PageHeader } from "@/components/layout/PageHeader";
import { KnowledgeDetailView } from "@/components/admin/KnowledgeDetailView";

export default async function AdminKnowledgeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Knowledge source" description="Provenance, checks, preview and lifecycle for one source." />
      <KnowledgeDetailView id={id} />
    </section>
  );
}
