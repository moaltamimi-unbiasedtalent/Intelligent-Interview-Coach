import { describe, expect, it } from "vitest";
import { returnDestination } from "@/lib/auth/return-destination";

describe("post-authentication return destination", () => {
  it.each(["/prepare", "/onboarding", "/workspaces/invite?token=abc%2Fdef", "/app?tab=one#section", "/admin"])('preserves valid local destination %s', (value) => {
    expect(returnDestination(value)).toBe(value);
    expect(new URL(returnDestination(value), "https://example.test").origin).toBe("https://example.test");
  });
  it.each([null, "", "//evil.test", "/\\evil.test", "/%2f%2fevil.test", "/%252f%252fevil.test", "/%5cevil", "/%255cevil", "/bad%", "/bad%00", "/x\n", "https://evil.test", "javascript:alert(1)", "/sign-in", "/%73ign-in", "/%2573ign-in", "/register?next=/prepare", "/forgot-password", "/reset-password", "/a/../admin"])('rejects unsafe destination %s', (value) => {
    expect(returnDestination(value)).toBe("/app");
  });
});
