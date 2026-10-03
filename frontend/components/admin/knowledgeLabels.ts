export const STATE_LABEL: Record<string, string> = {
  queued: "Queued for scanning", processing: "Scanning and parsing", review_required: "Awaiting review", approved: "Approved (not indexed)",
  indexing: "Indexing", indexed: "Indexed (not active)", active: "Active", rejected: "Rejected", failed: "Failed", retired: "Retired",
};
export const SCAN_LABEL: Record<string, string> = {
  not_scanned: "Not scanned", scan_passed: "Scan passed", scan_failed: "Scan flagged the file", scan_unavailable: "Scanner unavailable",
};
export const FAILURE_LABEL: Record<string, string> = {
  scan_failed: "The malware scan flagged the file", scan_unavailable: "No malware scanner is available", parse_failed: "The file could not be read",
  no_text: "No text could be extracted", no_chunks: "Nothing could be indexed", unavailable: "A required service was unavailable",
  internal_error: "Unexpected error",
};
export const REASON_LABEL: Record<string, string> = {
  provenance_insufficient: "Provenance insufficient", licence_not_permitted: "Licence does not permit use", quality_insufficient: "Quality insufficient",
  out_of_scope: "Out of scope", unsafe_content: "Unsafe content", duplicate: "Duplicate", other: "Other",
};
export const label = (v: string) => v.replace(/_/g, " ");
export const stateText = (s: string) => STATE_LABEL[s] ?? label(s);
