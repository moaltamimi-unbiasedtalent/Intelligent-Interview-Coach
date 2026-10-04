import { PageHeader } from "@/components/layout/PageHeader";
import { FlagsView } from "@/components/admin/FlagsView";

export default function AdminFlagsPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Feature flags" description="Code-defined flags with durable overrides. A flag can only restrict availability." />
      <FlagsView />
    </section>
  );
}
