import { PageHeader } from "@/components/layout/PageHeader";
import { JobDetailView } from "@/components/admin/JobDetailView";

export default async function AdminJobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Job" description="Safe job state, execution and failure diagnostics." />
      <JobDetailView id={id} />
    </section>
  );
}
