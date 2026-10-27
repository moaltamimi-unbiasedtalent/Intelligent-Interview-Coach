import { describe, expect, it } from "vitest";
import { completedPracticeRscAbort } from "../e2e/fixtures/navigationEvidence";

const observed = { code: "net::ERR_ABORTED", resource: "fetch", rsc: true, status: 200,
  contentType: "text/x-component", url: "http://localhost:3137/practice" };
const destination = "http://localhost:3137/practice";

describe("a cancelled RSC body is classified only after successful Practice navigation", () => {
  it("classifies the observed same-origin HTTP-200 navigation after explicit UI confirmation", () => {
    expect(completedPracticeRscAbort(observed, destination)).toBe(true);
  });
  it.each([
    ["image request", { resource: "image" }],
    ["optimizer URL", { url: "http://localhost:3137/_next/image" }],
    ["API request", { url: "http://localhost:3137/api/v1/practice" }],
    ["failed HTTP response", { status: 500 }],
    ["no HTTP response", { status: undefined }],
    ["real transport failure", { code: "net::ERR_CONNECTION_RESET" }],
    ["non-RSC response", { contentType: "application/json" }],
    ["non-RSC request", { rsc: false }],
    ["foreign origin", { url: "https://unexpected.invalid/practice" }],
    ["different route", { url: "http://localhost:3137/history" }],
    ["malformed URL", { url: "invalid" }],
  ])("never exempts %s", (_name, change) => {
    expect(completedPracticeRscAbort({ ...observed, ...change }, destination)).toBe(false);
  });
  it("refuses an otherwise matching abort without confirmed destination state", () => {
    expect(completedPracticeRscAbort(observed, null)).toBe(false);
    expect(completedPracticeRscAbort(observed, "http://localhost:3137/history")).toBe(false);
  });
});
