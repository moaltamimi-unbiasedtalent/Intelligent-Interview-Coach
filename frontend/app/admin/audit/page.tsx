import { PageHeader } from "@/components/layout/PageHeader";
import { AuditView } from "@/components/admin/AuditView";

export default function AdminAuditViewPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Audit" description="Privileged actions and denied access, with request ids." />
      <AuditView />
    </section>
  );
}
