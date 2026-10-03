import { PageHeader } from "@/components/layout/PageHeader";
import { LegalView } from "@/components/admin/LegalView";

export default function AdminLegalPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Legal" description="Legal document versions and recorded acceptance counts. Not a compliance measure." />
      <LegalView />
    </section>
  );
}
