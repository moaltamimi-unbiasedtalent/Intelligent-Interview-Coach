import { expect, test } from "@playwright/test";

import { runJourney } from "./journey/definition";
import { MockWorld } from "./journey/mockWorld";
import { MODE, MODE_LABEL, VARIANT, languagesToRun, makeEnv } from "./journey/env";

/**
 * 04D (REQ-CAND-01, DEMO-02, PG-06): the real-browser Candidate journey, once per selectable language, from ONE definition (./journey/definition.ts).
 *
 *   mocked (default, always on in CI):  E2E_PORT=3132 npx playwright test e2e/candidate-journey-04d.spec.ts
 *   real local stack:                   python scripts/e2e/journey_stack.py run          (offline fixtures, unique ports, temporary database)
 *   real hosted staging (NOT RUN):      see the docs at the top of scripts/e2e/journey_stack.py
 *
 * Evidence label for every result: MOCKED NETWORK or REAL STACK. Neither is live-model qualification.
 */

test.describe.configure({ mode: "serial" });

const languages = languagesToRun();

for (const [index, locale] of languages.entries()) {
  test(`candidate journey [${MODE_LABEL}] [${locale}]`, async ({ page, baseURL }) => {
    test.skip(VARIANT !== "healthy", `variant ${VARIANT} is covered by candidate-provider-04d.spec.ts`);
    test.setTimeout(MODE === "real" ? 180_000 : 90_000);
    test.info().annotations.push({ type: "evidence", description: MODE_LABEL });
    const env = makeEnv(locale, index);
    const world = new MockWorld();
    if (MODE === "mocked") await world.install(page);

    const result = await runJourney(page, env, baseURL ?? "http://localhost:3000");

    expect(result.opportunityId).toBeGreaterThan(0);
    expect(result.interviewStartRequests).toBe(1);
    if (MODE === "mocked") {
      // The mock served the journey; anything it had to answer with `{}` is UI drift to look at, so it is listed in the report rather than hidden.
      test.info().annotations.push({ type: "unmodelled-api-calls", description: [...new Set(world.unmocked)].join(", ") || "none" });
      expect(world.consumedInvitations.size).toBe(1);                       // the invitation was single use and consumed by exactly this registration
    }
  });
}

// The suite must not be vacuous: with Start Interview failing like the original defect, the very same journey has to fail at exactly that step.
if (MODE === "mocked") {
  test("self-check: the journey fails at START INTERVIEW when interview creation is unavailable", async ({ page, baseURL }) => {
    test.setTimeout(120_000);
    const world = new MockWorld();
    world.failInterviewCreate = true;
    await world.install(page);
    await expect(runJourney(page, makeEnv("en", 99), baseURL ?? "http://localhost:3000")).rejects.toThrow();
    expect(world.calls).toContain("POST /interviews");
    expect(world.calls.some((c) => c.endsWith("/answers"))).toBe(false);
  });
}
