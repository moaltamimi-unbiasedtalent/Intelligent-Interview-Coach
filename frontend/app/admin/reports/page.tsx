import { PageHeader } from "@/components/layout/PageHeader";
import { ReportsView } from "@/components/admin/ReportsView";

export default function AdminReportsPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Reports" description="Aggregate product, quality, operations, AI economics and mock commercial reporting." />
      <ReportsView />
    </section>
  );
}
