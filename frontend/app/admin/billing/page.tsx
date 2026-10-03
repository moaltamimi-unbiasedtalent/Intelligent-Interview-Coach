import { PageHeader } from "@/components/layout/PageHeader";
import { BillingView } from "@/components/admin/BillingView";

export default function AdminBillingPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Billing" description="MOCK BILLING, not live: simulated commercial metadata. No live payments are processed." />
      <BillingView />
    </section>
  );
}
