import { PageHeader } from "@/components/layout/PageHeader";
import { AIConfigDetailView } from "@/components/admin/AIConfigDetailView";

export default async function AdminAIConfigPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="AI configuration" description="Settings, validation, evaluation, approval and activation for one configuration version." />
      <AIConfigDetailView id={id} />
    </section>
  );
}
