import { PageHeader } from "@/components/layout/PageHeader";
import { ProvidersView } from "@/components/admin/ProvidersView";

export default function AdminProvidersViewPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Provider status" description="Configuration status only. Configured does not mean healthy." />
      <ProvidersView />
    </section>
  );
}
