/** Test-only recursive controls; inspect parsed synthetic export without retaining contents. */
const DENIED_KEYS = new Set([
  "password_hash", "token_hash", "storage_key", "content_hash", "checksum", "refresh_token", "access_token",
  "api_key", "prompt", "system_prompt", "internal_prompt", "session_token", "authorization", "provider_secret",
]);
const SECRET_CANARY = "SYNTH_PRIVATE_SECRET_CANARY";

export function noPrivateFields(value: unknown): boolean {
  if (typeof value === "string") return !value.includes(SECRET_CANARY);
  if (Array.isArray(value)) return value.every(noPrivateFields);
  if (value && typeof value === "object") return Object.entries(value as Record<string, unknown>).every(([k, v]) => !DENIED_KEYS.has(k.toLowerCase()) && noPrivateFields(v));
  return true;
}
