import { describe, expect, it } from "vitest";
import { noPrivateFields } from "../data_export_connected_e2e/privacy-assertions";

describe("synthetic export privacy controls", () => {
  it("allows legitimate caller content and usage token counts", () => {
    expect(noPrivateFields({ stories: [{ situation: "Candidate-owned story", practice_uses: [{ session_id: "s1" }] }], ai_usage: [{ input_tokens: 5 }] })).toBe(true);
  });
  it.each(["password_hash", "token_hash", "storage_key", "content_hash", "checksum", "refresh_token", "access_token", "api_key", "system_prompt", "session_token", "provider_secret"])('rejects nested sensitive field %s', (key) => {
    expect(noPrivateFields({ data: [{ nested: { [key]: "synthetic" } }] })).toBe(false);
  });
  it("rejects a private canary at any nesting depth", () => {
    expect(noPrivateFields({ data: [{ note: "SYNTH_PRIVATE_SECRET_CANARY" }] })).toBe(false);
  });
});
