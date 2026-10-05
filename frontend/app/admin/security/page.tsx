import { PageHeader } from "@/components/layout/PageHeader";
import { SecurityView } from "@/components/admin/SecurityView";

export default function AdminSecurityPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Security" description="Security events, audit history, incidents, in-app alerts and role approvals. Metadata only." />
      <SecurityView />
    </section>
  );
}
