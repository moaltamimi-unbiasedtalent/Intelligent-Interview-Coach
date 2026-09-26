"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { LoadingState } from "@/components/ui/States";
import { useT } from "@/components/i18n/I18nProvider";

type State = "verifying" | "ok" | "error";

export function VerifyEmailPanel() {
  const t = useT();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState<State>(token ? "verifying" : "error");
  const [message, setMessage] = useState<string>("");
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // verify exactly once (single-use token)
    api.auth
      .verifyEmail(token)
      .then((res) => {
        setState("ok");
        setMessage(res.message);
      })
      .catch((err) => {
        setState("error");
        setMessage(err instanceof ApiError ? err.message : t("auth.verifyLinkInvalid"));
      });
  }, [token, t]);

  return (
    <AuthCard
      title={t("auth.verifyTitle")}
      footer={
        <Link href="/sign-in" className="font-semibold text-accent hover:underline">
          {t("auth.goToSignIn")}
        </Link>
      }
    >
      {state === "verifying" ? <LoadingState label={t("auth.verifying")} /> : null}
      {state === "ok" ? <Alert tone="info">{message}</Alert> : null}
      {state === "error" ? (
        <Alert tone="danger">{message || t("auth.verifyLinkInvalid")}</Alert>
      ) : null}
    </AuthCard>
  );
}
