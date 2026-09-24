"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { AuthCard } from "./AuthCard";
import { Alert } from "@/components/ui/Alert";
import { LoadingState } from "@/components/ui/States";

type State = "verifying" | "ok" | "error";

export function VerifyEmailPanel() {
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
        setMessage(
          err instanceof ApiError ? err.message : "This verification link is invalid or has expired.",
        );
      });
  }, [token]);

  return (
    <AuthCard
      title="Email verification"
      footer={
        <Link href="/sign-in" className="font-semibold text-accent hover:underline">
          Go to sign in
        </Link>
      }
    >
      {state === "verifying" ? <LoadingState label="Verifying your email" /> : null}
      {state === "ok" ? <Alert tone="info">{message}</Alert> : null}
      {state === "error" ? (
        <Alert tone="danger">
          {message || "This verification link is invalid or has expired."}
        </Alert>
      ) : null}
    </AuthCard>
  );
}
