"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import Link from "@/components/ui/VerifiedLink";
import { useT } from "@/components/i18n/I18nProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { Input, Textarea } from "@/components/ui/Field";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { api } from "@/lib/api/client";
import type { SupportCategory, SupportTicketList } from "@/lib/api/types";
import { MESSAGE_MAX, SUBJECT_MAX, SUPPORT_CATEGORIES, categoryKey, statusKey } from "./supportLabels";

/** Pathname only: a query string or fragment may carry sensitive data and is never sent. */
function safeFrom(raw: string | null): string | undefined {
  const p = (raw ?? "").split("?")[0].split("#")[0];
  return p.startsWith("/") && p.length <= 200 ? p : undefined;
}

export function SupportHome() {
  const t = useT();
  const params = useSearchParams();
  const [category, setCategory] = useState<SupportCategory | "">("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [requestId, setRequestId] = useState(params.get("ref") ?? "");
  const [errors, setErrors] = useState<{ category?: string; subject?: string; message?: string }>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [list, setList] = useState<SupportTicketList | null>(null);
  const [listError, setListError] = useState(false);
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const firstError = useRef<HTMLElement | null>(null);

  const load = useCallback(() => {
    setListError(false);
    api.support.list(page).then(setList).catch(() => setListError(true));
  }, [page]);
  useEffect(load, [load]);
  useEffect(() => {
    if (created) noticeRef.current?.focus();
  }, [created]);

  const validate = () => {
    const e: typeof errors = {};
    if (!category) e.category = t("support.errCategory");
    if (!subject.trim()) e.subject = t("support.errRequired");
    else if (subject.trim().length > SUBJECT_MAX) e.subject = t("support.errSubjectLong");
    if (!message.trim()) e.message = t("support.errRequired");
    else if (message.trim().length > MESSAGE_MAX) e.message = t("support.errMessageLong");
    setErrors(e);
    return e;
  };

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setSubmitError(null);
    setCreated(null);
    const e = validate();
    if (Object.keys(e).length) {
      requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      return;
    }
    setBusy(true);
    try {
      const out = await api.support.create({
        category: category as SupportCategory,
        subject: subject.trim(),
        message: message.trim(),
        request_id: requestId.trim() || undefined,
        source_route: safeFrom(params.get("from")),
      });
      setCreated(out.public_id);
      setSubject("");
      setMessage("");
      setCategory("");
      setPage(1);
      load();
    } catch {
      // The write is never auto-retried; the text stays in the form.
      setSubmitError(t("support.errSubmit"));
    } finally {
      setBusy(false);
    }
  };

  const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;
  const describedBy = (id: string, err?: string) => (err ? `${id}-err` : undefined);

  return (
    <section>
      <PageHeader eyebrow={t("support.eyebrow")} title={t("support.title")} description={t("support.description")} />
      <p className="mb-4 max-w-reading text-sm text-muted">
        {t("support.noticeNoEmail")} {t("support.noticeNoPromise")}
      </p>

      <Card>
        <CardBody>
          <h2 className="text-lg font-semibold">{t("support.newTitle")}</h2>
          {created ? (
            <p ref={noticeRef} tabIndex={-1} role="status" className="my-3 rounded border border-border px-3 py-2 text-sm">
              {t("support.created", { ref: created })}{" "}
              <Link href={`/support/${created}`} className="font-semibold underline underline-offset-2">
                {t("support.openTicket")}
              </Link>
            </p>
          ) : null}
          <form onSubmit={submit} noValidate className="mt-3 grid max-w-reading gap-4">
            <div className="grid gap-1">
              <label htmlFor="support-category" className="text-sm font-medium">{t("support.categoryLabel")}</label>
              <select
                id="support-category"
                value={category}
                onChange={(e) => setCategory(e.target.value as SupportCategory | "")}
                aria-invalid={errors.category ? true : undefined}
                aria-describedby={describedBy("support-category", errors.category)}
                className="min-h-[44px] w-full rounded-lg border border-border bg-surface px-3 text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
              >
                <option value="">{t("support.categoryPlaceholder")}</option>
                {SUPPORT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{t(categoryKey(c))}</option>
                ))}
              </select>
              {errors.category ? <p id="support-category-err" className="text-sm text-danger">{errors.category}</p> : null}
            </div>
            <div className="grid gap-1">
              <label htmlFor="support-subject" className="text-sm font-medium">{t("support.subjectLabel")}</label>
              <Input
                id="support-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                aria-invalid={errors.subject ? true : undefined}
                aria-describedby={describedBy("support-subject", errors.subject)}
              />
              {errors.subject ? <p id="support-subject-err" className="text-sm text-danger">{errors.subject}</p> : null}
            </div>
            <div className="grid gap-1">
              <label htmlFor="support-message" className="text-sm font-medium">{t("support.messageLabel")}</label>
              <p id="support-message-hint" className="text-xs text-muted">{t("support.messageHint")}</p>
              <Textarea
                id="support-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                aria-invalid={errors.message ? true : undefined}
                aria-describedby={`support-message-hint${errors.message ? " support-message-err" : ""}`}
              />
              {errors.message ? <p id="support-message-err" className="text-sm text-danger">{errors.message}</p> : null}
            </div>
            <div className="grid gap-1">
              <label htmlFor="support-request-id" className="text-sm font-medium">{t("support.requestIdLabel")}</label>
              <p id="support-request-id-hint" className="text-xs text-muted">{t("support.requestIdHint")}</p>
              <Input id="support-request-id" value={requestId} onChange={(e) => setRequestId(e.target.value)} aria-describedby="support-request-id-hint" maxLength={64} />
            </div>
            {submitError ? <p role="alert" className="text-sm text-danger">{submitError}</p> : null}
            <div>
              <Button type="submit" disabled={busy} aria-busy={busy}>{busy ? t("support.sending") : t("support.submit")}</Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <h2 className="mb-2 mt-8 text-lg font-semibold">{t("support.listTitle")}</h2>
      {listError ? (
        <ErrorState variant="section" message={t("support.errLoad")} onRetry={load} retryLabel={t("support.retry")} />
      ) : !list ? (
        <LoadingState label={t("support.loading")} />
      ) : list.items.length === 0 ? (
        <p className="text-sm text-muted">{t("support.listEmpty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{t("support.listTitle")}</caption>
            <thead>
              <tr className="text-xs text-muted">
                {(["colSubject", "colTopic", "colStatus", "colUpdated"] as const).map((k) => (
                  <th key={k} scope="col" className="py-1 pr-4 font-medium">{t(`support.${k}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {list.items.map((it) => (
                <tr key={it.public_id} className="border-t border-border">
                  <th scope="row" className="py-2 pr-4 text-left font-medium [overflow-wrap:anywhere]">
                    <Link href={`/support/${it.public_id}`} className="underline underline-offset-2">{it.subject}</Link>
                  </th>
                  <td className="py-2 pr-4">{t(categoryKey(it.category))}</td>
                  <td className="py-2 pr-4">{t(statusKey(it.status))}</td>
                  <td className="py-2 pr-4">{it.updated_at ? new Date(it.updated_at).toLocaleString() : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <nav aria-label={t("support.listTitle")} className="mt-3 flex items-center gap-3 text-sm">
            <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("support.previous")}</Button>
            <span role="status">{t("support.pageOf", { page: String(list.page), pages: String(pages) })}</span>
            <Button variant="ghost" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t("support.next")}</Button>
          </nav>
        </div>
      )}
    </section>
  );
}
