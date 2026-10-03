import { PageHeader } from "@/components/layout/PageHeader";
import { IntegrationsView } from "@/components/admin/IntegrationsView";

export default function AdminIntegrationsPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Integrations" description="External connections: configuration, runtime state and health. Credentials are never shown." />
      <IntegrationsView />
    </section>
  );
}
