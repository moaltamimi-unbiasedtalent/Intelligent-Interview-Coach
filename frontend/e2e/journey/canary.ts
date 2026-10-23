/**
 * A CANARY provider key for the key-hazard guard (04D). It is a test value, never a credential. The web server the suite starts is given it as OPENROUTER_API_KEY (see playwright.config.ts), so
 * the guard can prove that a key present in the server environment never reaches the browser bundle or any page. If a real key is already exported in the shell, that value is the canary instead
 * (the guard then proves the same about the real value; it is never printed).
 */
export const KEY_CANARY = "sk-or-v1-0123456789abcdef0123456789abcdef0123456789abcdef04D0CANARYWEB";

export function configuredKeyValue(): string {
  return process.env.OPENROUTER_API_KEY && process.env.OPENROUTER_API_KEY.length >= 8 ? process.env.OPENROUTER_API_KEY : KEY_CANARY;
}
