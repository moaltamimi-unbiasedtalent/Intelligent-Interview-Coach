// The Command Center sections, in display order. The permission per section mirrors the route (src/api/routes/admin_command_center.py) and is a UX convenience only:
// the server authorises every request, and a 403 renders as "Not permitted", never as an error crash.
import { P } from "./capabilities";

export type CommandCenterSectionPath = "health" | "ai-operations" | "jobs" | "knowledge" | "alerts" | "security-signals" | "candidate-activity";

export interface CommandCenterSectionSpec {
  path: CommandCenterSectionPath;
  title: string;
  permission: string;
  /** Why this section exists (what question it answers), in one sentence. */
  purpose: string;
}

export const COMMAND_CENTER_SECTIONS: readonly CommandCenterSectionSpec[] = [
  { path: "health", title: "Platform health", permission: P.overview, purpose: "Is the platform up, is work being processed and is anything paused?" },
  { path: "ai-operations", title: "AI operations", permission: P.ai, purpose: "How much AI work runs, where it fails and what it costs (known cost only)?" },
  { path: "jobs", title: "Job queue health", permission: P.jobsRead, purpose: "Is background work waiting, stuck or failing?" },
  { path: "knowledge", title: "Knowledge readiness", permission: P.knowledge, purpose: "Is governed knowledge approved, indexed and healthy?" },
  { path: "alerts", title: "Alerts", permission: P.securityRead, purpose: "How many alerts need attention, by category and severity?" },
  { path: "security-signals", title: "Auth and security signals", permission: P.securityRead, purpose: "Counts of authentication and access signals (no actor, address or e-mail)." },
  { path: "candidate-activity", title: "Candidate activity", permission: P.reportsRead, purpose: "Aggregate candidate activity; small cohorts are suppressed." },
];

export const AI_OPERATIONS_SECTION = COMMAND_CENTER_SECTIONS[1];
