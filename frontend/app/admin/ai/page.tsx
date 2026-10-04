import { PageHeader } from "@/components/layout/PageHeader";
import { AIView } from "@/components/admin/AIView";

export default function AdminAIPage() {
  return (
    <section>
      <PageHeader eyebrow="Platform operations" title="AI and models" description="Governed model configuration: evaluated, second-approved and reversible. No live model is called here." />
      <AIView />
    </section>
  );
}
