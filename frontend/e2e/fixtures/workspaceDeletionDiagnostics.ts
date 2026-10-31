/** Bounded synthetic Workspace navigation observations; never persist event payloads or URLs. */
export type WorkspaceEvent = "confirm_matches" | "confirm_mismatch" | "delete_request" | "delete_200_fake_absent" | "delete_other" | "route_data_request" | "route_data_200" | "route_data_other" | "url_list" | "url_detail" | "url_other" | "dialog_visible" | "dialog_hidden" | "detail_visible" | "detail_hidden" | "console_http_error" | "console_other" | "page_error" | "assertion_passed" | "assertion_failed";
const allowed = new Set<WorkspaceEvent>(["confirm_matches", "confirm_mismatch", "delete_request", "delete_200_fake_absent", "delete_other", "route_data_request", "route_data_200", "route_data_other", "url_list", "url_detail", "url_other", "dialog_visible", "dialog_hidden", "detail_visible", "detail_hidden", "console_http_error", "console_other", "page_error", "assertion_passed", "assertion_failed"]);
export class WorkspaceDeletionDiagnostics {
  private readonly start = performance.now();
  private events: Array<{ event: WorkspaceEvent; elapsed_ms: number }> = [];
  private total = 0;
  record(event: WorkspaceEvent) {
    if (!allowed.has(event)) return;
    this.total++;
    if (this.events.length < 100) this.events.push({ event, elapsed_ms: Math.max(0, Math.round(performance.now() - this.start)) });
  }
  snapshot() { return { limit: 100, total: this.total, dropped: this.total - this.events.length, events: this.events.map(e => ({ ...e })) }; }
}
