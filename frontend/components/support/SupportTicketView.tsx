"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "@/components/ui/VerifiedLink";
import { useT } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api/client";
import type { SupportTicketDetail } from "@/lib/api/types";
import { MESSAGE_MAX, categoryKey, statusKey } from "./supportLabels";

export function SupportTicketView({ publicId }: { publicId: string }) {
  const t = useT();
  const [ticket, setTicket] = useState<SupportTicketDetail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">("loading");
  const [reply, setReply] = useState("");
  const [replyError, setReplyError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setState("loading");
    api.support
      .get(publicId)
      .then((d) => {
        setTicket(d);
        setState("ready");
      })
      .catch((e) => setState(e instanceof ApiError && e.status === 404 ? "missing" : "error"));
  }, [publicId]);
  useEffect(load, [load]);

  const send = async (ev: FormEvent) => {
    ev.preventDefault();
    const text = reply.trim();
    if (!text) return setReplyError(t("support.errRequired"));
    if (text.length > MESSAGE_MAX) return setReplyError(t("support.errMessageLong"));
    setBusy(true);
    setReplyError(null);
    try {
      setTicket(await api.support.reply(publicId, text));
      setReply("");
    } catch {
      setReplyError(t("support.errReply")); // never auto-retried; the text stays in the box
    } finally {
      setBusy(false);
    }
  };

  const back = (
    <p className="mb-3">
      <Link href="/support" className="text-sm underline underline-offset-2">{t("support.back")}</Link>
    </p>
  );
  if (state === "loading") return <LoadingState label={t("support.loading")} />;
  if (state === "missing")
    return <section>{back}<h1 className="text-xl font-semibold">{t("support.notFound")}</h1></section>;
  if (state === "error" || !ticket)
    return <section>{back}<ErrorState message={t("support.errLoad")} onRetry={load} retryLabel={t("support.retry")} /></section>;

  return (
    <section>
      {back}
      <PageHeader eyebrow={t("support.title")} title={ticket.subject} description={`${t("support.reference")}: ${ticket.public_id}`} />
      <dl className="mb-6 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-muted">{t("support.colTopic")}</dt>
        <dd>{t(categoryKey(ticket.category))}</dd>
        <dt className="text-muted">{t("support.colStatus")}</dt>
        <dd>{t(statusKey(ticket.status))}</dd>
        <dt className="text-muted">{t("support.colUpdated")}</dt>
        <dd>{ticket.updated_at ? new Date(ticket.updated_at).toLocaleString() : ""}</dd>
      </dl>

      <h2 className="mb-2 text-lg font-semibold">{t("support.conversation")}</h2>
      <ol className="grid gap-3" aria-label={t("support.conversation")}>
        {ticket.messages.map((m) => (
          <li key={m.id} className="rounded-lg border border-border bg-surface px-4 py-3">
            <p className="text-xs font-semibold text-muted">
              {m.author_kind === "support" ? t("support.team") : t("support.you")}
              {m.created_at ? ` · ${new Date(m.created_at).toLocaleString()}` : ""}
            </p>
            {/* Plain text only: React escapes markup, so HTML/script typed by anyone is shown as text. */}
            <p className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere]">{m.body}</p>
          </li>
        ))}
      </ol>

      {ticket.can_reply ? (
        <form onSubmit={send} noValidate className="mt-6 grid max-w-reading gap-2">
          <label htmlFor="support-reply" className="text-sm font-medium">{t("support.replyLabel")}</label>
          <Textarea
            id="support-reply"
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            aria-invalid={replyError ? true : undefined}
            aria-describedby={replyError ? "support-reply-err" : undefined}
          />
          {replyError ? <p id="support-reply-err" role="alert" className="text-sm text-danger">{replyError}</p> : null}
          <div><Button type="submit" disabled={busy}>{t("support.replySend")}</Button></div>
        </form>
      ) : (
        <p className="mt-6 text-sm text-muted">{t("support.replyClosed")}</p>
      )}
    </section>
  );
}
