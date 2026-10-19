import { PageHeader } from "@/components/layout/PageHeader";
import { SpeechView } from "@/components/admin/SpeechView";

export default function AdminSpeechPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="Speech" description="Governed speech providers: selection and policy only. Server speech is not active." />
      <SpeechView />
    </section>
  );
}
