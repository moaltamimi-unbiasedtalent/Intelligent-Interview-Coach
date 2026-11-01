import { describe, expect, it } from "vitest";
import { assessRefusal, type RefusalInput } from "../data_export_connected_e2e/auth-refusal";

const valid = (): RefusalInput => ({ scenario: "anonymous", status: 401, contentType: "application/json", attachment: null,
  body: { error: { code: "unauthorized", message: "Authentication required.", request_id: "synthetic-request" } }, logoutSuccess: null });

describe("export authentication refusal", () => {
  it("accepts the exact anonymous and post-logout contracts", () => {
    expect(assessRefusal(valid()).passed).toBe(true);
    expect(assessRefusal({ ...valid(), scenario: "logged_out", logoutSuccess: true }).passed).toBe(true);
  });
  it.each([0, 200, 302, 403, 404, 422, 429, 500, 503])("rejects incorrect status %s", status => {
    expect(assessRefusal({ ...valid(), status }).passed).toBe(false);
    if ([403, 404, 422, 429, 500, 503].includes(status)) expect(status !== 200).toBe(true); // old predicate would wrongly pass
  });
  it.each([
    ["wrong code", { error: { code: "other", message: "Authentication required.", request_id: "r" } }],
    ["missing code", { error: { message: "Authentication required.", request_id: "r" } }],
    ["malformed", { error: [] }], ["export", { ...valid().body as object, stories: [] }],
    ["bad id", { error: { code: "unauthorized", message: "Authentication required.", request_id: 42 } }],
    ["marker", { error: { code: "unauthorized", message: "SYNTH_FOREIGN_WILLOW", request_id: "r" } }],
    ["invalid json", null],
  ])("rejects %s body", (_label, body) => expect(assessRefusal({ ...valid(), body }).passed).toBe(false));
  it("rejects HTML, attachments, and unsuccessful logout", () => {
    expect(assessRefusal({ ...valid(), contentType: "text/html" }).passed).toBe(false);
    expect(assessRefusal({ ...valid(), attachment: 'attachment; filename="data.json"' }).passed).toBe(false);
    expect(assessRefusal({ ...valid(), scenario: "logged_out", logoutSuccess: false }).passed).toBe(false);
  });
});
