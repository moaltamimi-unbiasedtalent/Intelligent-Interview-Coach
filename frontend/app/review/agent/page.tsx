import type { Metadata } from "next";
import { Suspense } from "react";
import { AgentInspector } from "@/components/agent/AgentInspector";
import { LoadingState } from "@/components/ui/States";

export const metadata: Metadata = { title: "Agent Inspector" };

export default function AgentInspectorPage() {
  // Suspense boundary: the inspector reads the run id from the URL (useSearchParams).
  return (
    <Suspense fallback={<LoadingState label="Loading Agent Inspector" />}>
      <AgentInspector />
    </Suspense>
  );
}
