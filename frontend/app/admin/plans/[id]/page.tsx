import { PageHeader } from "@/components/layout/PageHeader";
import { PlanDetailView } from "@/components/admin/PlanDetailView";

export default async function AdminPlanDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Plan version" description="Typed entitlement values for one version." />
      <PlanDetailView versionId={Number(id)} />
    </section>
  );
}
