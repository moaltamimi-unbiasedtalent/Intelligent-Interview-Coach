import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";

export const metadata: Metadata = { title: "Review & Diagnostics" };

const AREAS = [
  { href: "/review/agent", name: "Agent Inspector", note: "Safe action traces for agent runs.", status: "Available" },
  { href: "/review/rag", name: "RAG Inspector", note: "Retrieval lanes, evidence and citations.", status: "Legacy diagnostic" },
  { href: "/review/evaluation", name: "Evaluation", note: "Retrieval metrics and optional RAGAS.", status: "Evaluation tooling available" },
];

export default function ReviewPage() {
  return (
    <section>
      <PageHeader
        eyebrow="For reviewers & developers"
        title="Review & Diagnostics"
        description="Technical surfaces kept out of the candidate flow. Slightly more technical, same design system."
      />
      <div className="grid gap-4 sm:grid-cols-3">
        {AREAS.map((a) => (
          <Link key={a.href} href={a.href} className="block focus-visible:outline-none">
            <Card className="h-full transition-colors hover:border-accent">
              <CardBody className="grid gap-1.5">
                <h2 className="text-base font-semibold">{a.name}</h2>
                <p className="text-sm text-muted">{a.note}</p>
                <span className="mt-1 text-xs text-muted">{a.status}</span>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
}
