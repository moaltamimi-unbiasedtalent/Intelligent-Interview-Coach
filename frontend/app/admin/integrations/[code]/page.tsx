import { PageHeader } from "@/components/layout/PageHeader";
import { IntegrationDetailView } from "@/components/admin/IntegrationDetailView";

export default async function AdminIntegrationDetailPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Integration" description="Safe configuration metadata and manual connection test." />
      <IntegrationDetailView code={code} />
    </section>
  );
}
