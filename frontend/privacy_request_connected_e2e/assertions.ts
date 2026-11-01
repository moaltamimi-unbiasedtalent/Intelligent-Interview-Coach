export const requestFields = ["created_at", "public_id", "request_type", "result_category", "status", "type_label", "updated_at"];
export function validView(input: unknown): boolean {
  if (!input || typeof input !== "object" || Array.isArray(input)) return false;
  const value = input as Record<string, unknown>;
  return JSON.stringify(Object.keys(value).sort()) === JSON.stringify(requestFields) && typeof value.public_id === "string" && /^[0-9a-f]{32}$/.test(value.public_id) && value.request_type === "correction" && value.status === "submitted" && value.result_category === null && typeof value.type_label === "string" && typeof value.created_at === "string" && (typeof value.updated_at === "string" || value.updated_at === null);
}
export function validRefusal(input: {status:number; data:unknown}, status:number, code:string): boolean {
  if (input.status !== status || !input.data || typeof input.data !== "object" || Array.isArray(input.data)) return false;
  const body=input.data as Record<string, unknown>;
  if (Object.keys(body).length !== 1 || !body.error || typeof body.error !== "object" || Array.isArray(body.error)) return false;
  const error=body.error as Record<string, unknown>;
  return error.code === code && typeof error.message === "string" && typeof error.request_id === "string" && error.request_id.length > 0;
}
