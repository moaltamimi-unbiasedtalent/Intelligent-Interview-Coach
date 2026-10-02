import { PageHeader } from "@/components/layout/PageHeader";
import { SupportQueueView } from "@/components/admin/SupportQueueView";

export default function AdminSupportPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Support" description="Customer support queue. Candidate private content is never shown here." />
      <SupportQueueView />
    </section>
  );
}
