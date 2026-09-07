import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";

export const metadata: Metadata = { title: "Sources" };

const CATEGORIES = [
  { name: "Occupation profiles", note: "What roles typically require, by level." },
  { name: "Skills & competency frameworks", note: "The competencies employers look for." },
  { name: "Labour-market context", note: "Regional demand and expectations." },
  { name: "Compensation references", note: "Benchmarks used for context, never advice." },
];

export default function SourcesPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Trust"
        title="Career evidence"
        description="Your preparation is grounded in curated, public career evidence — not opinions. You can always see where guidance comes from."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        {CATEGORIES.map((c) => (
          <Card key={c.name}>
            <CardBody>
              <h2 className="text-base font-semibold">{c.name}</h2>
              <p className="mt-1 text-sm text-muted">{c.note}</p>
            </CardBody>
          </Card>
        ))}
      </div>
      <p className="mt-6 text-xs text-muted">
        DEMO categories. Live source details are connected in a later phase.
      </p>
    </section>
  );
}
