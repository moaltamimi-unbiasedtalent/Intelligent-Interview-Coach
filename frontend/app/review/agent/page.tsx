import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Agent Inspector" };

export default function AgentInspectorPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Review & Diagnostics"
        title="Agent Inspector"
        description="Safe action traces — tools, retrieval, sources, approvals, latency and cost. Never chain-of-thought, prompts or secrets."
      />
      <EmptyState
        title="Agent runs will appear here once the Sprint 4 agent is enabled"
        description="The agent (LangGraph) is planned for a later Sprint 4 phase. No agent metrics are shown until real runs exist — nothing is fabricated."
      />
    </section>
  );
}
