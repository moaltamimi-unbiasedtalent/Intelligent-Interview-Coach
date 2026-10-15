import { PageHeader } from "@/components/layout/PageHeader";
import { BillingWorkspace } from "@/components/admin/BillingWorkspace";

export default function AdminBillingPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Billing" description="Provider billing operations (offline-qualified, not operationally active) and MOCK BILLING records. No live payments are processed." />
      <BillingWorkspace />
    </section>
  );
}
