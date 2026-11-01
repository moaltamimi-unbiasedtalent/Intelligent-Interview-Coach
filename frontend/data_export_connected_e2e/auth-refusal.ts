import { noPrivateFields } from "./privacy-assertions";

export type RefusalInput = {
  scenario: "anonymous" | "logged_out";
  status: number;
  contentType: string | null;
  attachment: string | null;
  body: unknown;
  logoutSuccess: boolean | null;
};
export type RefusalFacts = {
  scenario: "anonymous" | "logged_out";
  status: number;
  classification: "unauthorized" | "unexpected";
  envelope_valid: boolean;
  export_absent: boolean;
  attachment_absent: boolean;
  logout_success: boolean | null;
  passed: boolean;
};

/** Produce only allowlisted facts; the response object remains transient. */
export function assessRefusal(input: RefusalInput): RefusalFacts {
  const object = input.body && typeof input.body === "object" && !Array.isArray(input.body) ? input.body as Record<string, unknown> : null;
  const error = object?.error && typeof object.error === "object" && !Array.isArray(object.error) ? object.error as Record<string, unknown> : null;
  const classification = error?.code === "unauthorized" ? "unauthorized" : "unexpected";
  const envelope = !!object && !!error && Object.keys(object).length === 1 && Object.keys(error).sort().join(",") === "code,message,request_id" &&
    error.code === "unauthorized" && error.message === "Authentication required." && typeof error.request_id === "string" && error.request_id.length > 0;
  const exportAbsent = !!object && !["format", "stories", "opportunities", "interviews", "data", "scope", "account"].some(k => k in object) &&
    noPrivateFields(object) && !["SYNTH_SELECTED_CEDAR", "SYNTH_UNSELECTED_MAPLE", "SYNTH_FOREIGN_WILLOW"].some(marker => JSON.stringify(object).includes(marker));
  const attachmentAbsent = input.attachment === null;
  const content = input.contentType?.split(";", 1)[0].trim().toLowerCase() === "application/json";
  const logout = input.scenario === "anonymous" ? input.logoutSuccess === null : input.logoutSuccess === true;
  const passed = input.status === 401 && content && envelope && exportAbsent && attachmentAbsent && logout;
  return { scenario: input.scenario, status: Number.isInteger(input.status) && input.status >= 0 && input.status <= 599 ? input.status : 0,
    classification, envelope_valid: envelope && content, export_absent: exportAbsent, attachment_absent: attachmentAbsent,
    logout_success: input.scenario === "anonymous" ? null : input.logoutSuccess === true, passed: !!passed };
}
