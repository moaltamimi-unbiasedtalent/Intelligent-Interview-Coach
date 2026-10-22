import { readFileSync } from "node:fs";

import fixtures from "./fixtures.json";

/**
 * Shared environment for the 04D Candidate journey. ONE journey definition (definition.ts) runs in two modes:
 *   mocked : the network is mocked at the page (mockWorld.ts); always on in CI; label "MOCKED NETWORK".
 *   real   : no mocks; the same steps against a real stack (local launcher, or a hosted staging stack via BASE_URL / JOURNEY_API_URL); label "REAL STACK".
 * Every report line states which one produced it. Neither is live-model qualification: the real local stack answers from offline fixtures.
 */

export type JourneyMode = "mocked" | "real";
export type JourneyVariant = "healthy" | "provider_down" | "keyless";

/** The seven selectable Candidate languages (Russian is preserved in the product but excluded from R1.0 selection). */
export const JOURNEY_LANGUAGES = ["en", "de", "fr", "es", "it", "pt", "nl"] as const;
export type JourneyLocale = (typeof JOURNEY_LANGUAGES)[number];

export const FIXTURES = fixtures;

export const MODE: JourneyMode = process.env.JOURNEY_MODE === "real" ? "real" : "mocked";
export const VARIANT: JourneyVariant = (["healthy", "provider_down", "keyless"] as const).find((v) => v === process.env.JOURNEY_VARIANT) ?? "healthy";
/** The AI mode the stack under test is EXPECTED to report (default offline: fixtures answer). A hosted stack with a governed live budget sets JOURNEY_EXPECT_AI_MODE=live; this suite never decides a budget. */
export const EXPECTED_AI_MODE: "live" | "offline" = process.env.JOURNEY_EXPECT_AI_MODE === "live" ? "live" : "offline";
export const MODE_LABEL = MODE === "real" ? "REAL STACK (offline fixtures unless the stack says otherwise)" : "MOCKED NETWORK";

/** Languages to run: all seven by default; JOURNEY_LANGUAGES=en,de narrows (hosted runs are rate limited per IP: see scripts/e2e/journey_stack.py). */
export function languagesToRun(): JourneyLocale[] {
  const raw = (process.env.JOURNEY_LANGUAGES ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const picked = raw.length ? JOURNEY_LANGUAGES.filter((l) => raw.includes(l)) : [...JOURNEY_LANGUAGES];
  return picked.length ? picked : [...JOURNEY_LANGUAGES];
}

/** Invitation codes for real mode: a JSON file {"codes": [...]}, one single-use code per language (+1 spare). Never printed. */
export function realInvitationCodes(): string[] {
  const file = process.env.JOURNEY_INVITATIONS_FILE;
  if (!file) throw new Error("JOURNEY_MODE=real needs JOURNEY_INVITATIONS_FILE (see scripts/e2e/journey_stack.py)");
  const parsed = JSON.parse(readFileSync(file, "utf8")) as { codes?: unknown };
  if (!Array.isArray(parsed.codes) || !parsed.codes.every((c) => typeof c === "string" && c.length > 0)) throw new Error("JOURNEY_INVITATIONS_FILE must contain {\"codes\": [string, ...]}");
  return parsed.codes as string[];
}

/** A valid code the MOCK accepts (single use, like the server). It is a test value, not a credential. */
export const MOCK_INVITATION_PREFIX = "mock-invitation-";

export interface JourneyEnv {
  mode: JourneyMode;
  variant: JourneyVariant;
  locale: JourneyLocale;
  invitationCode: string;
  email: string;
  password: string;
  displayName: string;
  /** The hosted-like uninvited probe runs once per run (it counts against the per-IP registration limit). */
  probeUninvited: boolean;
}

let runId = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;

export function makeEnv(locale: JourneyLocale, index: number): JourneyEnv {
  const codes = MODE === "real" ? realInvitationCodes() : [];
  return {
    mode: MODE,
    variant: VARIANT,
    locale,
    invitationCode: MODE === "real" ? codes[index] ?? codes[0] : `${MOCK_INVITATION_PREFIX}${locale}`,
    email: `journey-${locale}-${runId}@${FIXTURES.candidate.emailDomain}`,
    password: FIXTURES.candidate.password,
    displayName: FIXTURES.candidate.displayName,
    probeUninvited: index === 0,
  };
}
