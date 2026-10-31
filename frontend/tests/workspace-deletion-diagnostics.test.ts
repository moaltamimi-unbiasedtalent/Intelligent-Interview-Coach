import { describe, expect, it } from "vitest";
import { WorkspaceDeletionDiagnostics, type WorkspaceEvent } from "../e2e/fixtures/workspaceDeletionDiagnostics";

describe("Workspace deletion diagnostics", () => {
  it("allowlists events and bounds retention without recording arbitrary text", () => {
    const diag = new WorkspaceDeletionDiagnostics();
    diag.record("credential-canary" as WorkspaceEvent);
    for (let i = 0; i < 107; i++) diag.record("delete_request");
    const result = diag.snapshot();
    expect(result.total).toBe(107); expect(result.events).toHaveLength(100); expect(result.dropped).toBe(7);
    expect(JSON.stringify(result)).not.toContain("credential-canary");
    result.events[0].event = "page_error";
    expect(diag.snapshot().events[0].event).toBe("delete_request");
  });
});
