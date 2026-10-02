import type { SupportCategory, SupportStatus } from "@/lib/api/types";

/** Canonical category keys (the server validates the same list). Labels are localized via i18n keys. */
export const SUPPORT_CATEGORIES: SupportCategory[] = [
  "account_login", "opportunity", "prepare", "practice_interview", "documents", "ai_response",
  "billing", "privacy", "accessibility", "technical", "data_issue", "other",
];

export const categoryKey = (c: SupportCategory) => `support.cat_${c}`;
export const statusKey = (s: SupportStatus) => `support.status_${s}`;

export const SUBJECT_MAX = 200;
export const MESSAGE_MAX = 5000;
