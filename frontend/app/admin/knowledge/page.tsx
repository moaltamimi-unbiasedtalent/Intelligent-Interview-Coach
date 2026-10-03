import { PageHeader } from "@/components/layout/PageHeader";
import { KnowledgeView } from "@/components/admin/KnowledgeView";

export default function AdminKnowledgePage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Knowledge" description="Governed knowledge sources: scan, review, approve, index and activate. Platform knowledge only." />
      <KnowledgeView />
    </section>
  );
}
