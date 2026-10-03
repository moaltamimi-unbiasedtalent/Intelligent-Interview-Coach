import { PageHeader } from "@/components/layout/PageHeader";
import { PrivacyView } from "@/components/admin/PrivacyView";

export default function AdminPrivacyPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Privacy" description="Privacy request queue and workflow. Candidate private content is never shown here." />
      <PrivacyView />
    </section>
  );
}
