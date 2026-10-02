"use client";

import type { ReactNode } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { ConfirmDialogBase } from "./ConfirmDialogBase";

/** Localized confirmation dialog for candidate screens (see ConfirmDialogBase for the behaviour contract). */
export function ConfirmDialog({
  cancelLabel,
  ...props
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  testId?: string;
}) {
  const t = useT();
  return <ConfirmDialogBase {...props} cancelLabel={cancelLabel ?? t("common.cancel")} busyLabel={t("dataPrivacy.working")} />;
}
