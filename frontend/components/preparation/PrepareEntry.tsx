"use client";

import { useCapabilities } from "@/lib/useCapabilities";
import { LoadingState } from "@/components/ui/States";
import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";
import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";

/**
 * Deployment-controlled cutover (Phase 9): when the backend advertises
 * `agent_coach_enabled`, /prepare uses the LangGraph-powered Agent Coach; otherwise
 * it stays on the proven deterministic Career flow (safe rollback). This is NOT a
 * user-facing "agent/legacy" toggle.
 */
export function PrepareEntry() {
  const { capabilities, loading } = useCapabilities();
  if (loading) return <LoadingState label="Loading your preparation workspace" />;
  return capabilities.agent_coach_enabled ? <AgentPrepareWorkspace /> : <PrepareWorkspace />;
}
