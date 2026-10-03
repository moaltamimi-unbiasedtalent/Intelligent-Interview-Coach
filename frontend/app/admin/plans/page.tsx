import { PageHeader } from "@/components/layout/PageHeader";
import { PlansView } from "@/components/admin/PlansView";

export default function AdminPlansPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Plans" description="Plan versions and their entitlements. No prices or payments." />
      <PlansView />
    </section>
  );
}
