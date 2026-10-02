import { PageHeader } from "@/components/layout/PageHeader";
import { CommandCenter } from "@/components/admin/CommandCenter";

export default function AdminPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Platform operations"
        title="Command Center"
        description="Operational metadata only. No candidate-private content is accessible here."
      />
      <CommandCenter />
    </section>
  );
}
