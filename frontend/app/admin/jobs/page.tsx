import { PageHeader } from "@/components/layout/PageHeader";
import { JobsView } from "@/components/admin/JobsView";

export default function AdminJobsPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Jobs" description="Background job queue, workers and diagnostics. Job input is never shown." />
      <JobsView />
    </section>
  );
}
