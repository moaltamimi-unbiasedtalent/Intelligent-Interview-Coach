"use client";

import { useEffect, useState } from "react";
import { useCapabilities } from "@/lib/useCapabilities";
import { LoadingState } from "@/components/ui/States";
import { PrepareWorkspace } from "@/components/preparation/PrepareWorkspace";
import { AgentPrepareWorkspace } from "@/components/agent/AgentPrepareWorkspace";
import { clearPrepareDraft, readPrepareDraft } from "@/lib/prepareDraft";

/**
 * Deployment-controlled cutover (Phase 9): when the backend advertises
 * `agent_coach_enabled`, /prepare uses the LangGraph-powered Agent Coach; otherwise
 * it stays on the proven deterministic Career flow (safe rollback). This is NOT a
 * user-facing "agent/legacy" toggle.
 *
 * A transient Home → Prepare draft (if any) is read ONCE here and handed to whichever
 * experience is active — Home never needs to know which one that is. The draft value
 * lives in component state from this point, so it is cleared from storage promptly
 * (§10) while remaining available for the active workspace to consume (§11).
 */
export function PrepareEntry() {
  const { capabilities, loading } = useCapabilities();
  const [initialDraft] = useState(() => readPrepareDraft());

  // The value is captured above; remove it from storage so it can't leak into a
  // later visit. The active workspace still receives it via props.
  useEffect(() => {
    clearPrepareDraft();
  }, []);

  if (loading) return <LoadingState label="Loading your preparation workspace" />;
  return capabilities.agent_coach_enabled ? (
    <AgentPrepareWorkspace initialDraft={initialDraft} />
  ) : (
    <PrepareWorkspace initialDraft={initialDraft} />
  );
}
