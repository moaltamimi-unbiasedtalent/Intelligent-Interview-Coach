import { PageHeader } from "@/components/layout/PageHeader";
import { ConfigurationView } from "@/components/admin/ConfigurationView";

export default function AdminConfigurationPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Configuration" description="Durable platform pause. Shared by every process and restart-safe." />
      <ConfigurationView />
    </section>
  );
}
