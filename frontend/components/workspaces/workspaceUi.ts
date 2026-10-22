import { ApiError } from "@/lib/api/errors";

/** Interface label key for a workspace role. Unknown values degrade to the plain member label, never raw text. */
export function roleKey(role: string | undefined): string {
  if (role === "workspace_owner") return "wsMgmt.roleOwner";
  if (role === "workspace_admin") return "wsMgmt.roleAdmin";
  return "wsMgmt.roleMember";
}

/**
 * Localized message key for a workspace action that failed. The workspace API answers with calm domain statuses (403 role,
 * 404 not visible, 409 state, 422 input), so the generic "already being processed" wording of the shared taxonomy would be wrong
 * here. Connectivity problems keep the shared, truthful wording.
 */
export function workspaceErrorKey(error: unknown): string {
  if (!(error instanceof ApiError)) return "wsMgmt.errGeneric";
  switch (error.status) {
    case 403:
      return "wsMgmt.errForbidden";
    case 404:
      return "wsMgmt.errNotFound";
    case 409:
      return "wsMgmt.errConflict";
    case 422:
    case 400:
      return "wsMgmt.errValidation";
    default:
      break;
  }
  if (error.kind === "offline") return "states.offline";
  if (error.kind === "unreachable") return "states.serviceUnreachable";
  if (error.kind === "unauthenticated") return "states.sessionExpired";
  return "wsMgmt.errGeneric";
}

export function resourceTypeKey(resourceType: string): string {
  return resourceType === "story" ? "wsMgmt.typeStory" : "wsMgmt.typeReport";
}

export interface ShareableItem {
  id: string;
  label: string;
}

/** The caller's OWN items of one shareable type, for the share picker. Reports: completed interviews only. */
export async function loadShareableItems(
  type: "story" | "interview_report",
  api: {
    stories: { list: () => Promise<{ stories: Array<{ id: number; title: string }> }> };
    history: { list: () => Promise<{ interviews: Array<Record<string, unknown>> }> };
  },
): Promise<ShareableItem[]> {
  if (type === "story") {
    const r = await api.stories.list();
    return r.stories.map((s) => ({ id: String(s.id), label: s.title }));
  }
  const r = await api.history.list();
  return r.interviews
    .filter((i) => i.status === undefined || i.status === null || i.status === "completed")
    .map((i) => ({ id: String(i.id), label: `${String(i.target_role ?? "")} #${String(i.id)}`.trim() }));
}
