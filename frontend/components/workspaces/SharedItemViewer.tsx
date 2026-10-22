"use client";

import { useEffect, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";
import type { SharedResourceView } from "@/lib/api/types";
import { resourceTypeKey } from "./workspaceUi";

type Status = "loading" | "ready" | "gone";

function text(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  return null;
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string" && v.trim().length > 0) : [];
}

/**
 * Read-only view of ONE explicitly shared item. The server re-checks the share on every request, so a revoked, removed or
 * deleted item answers "not found" and this component says it is no longer shared (it never keeps a cached copy). Only the
 * bounded VIEW projection is rendered, as plain text (never HTML).
 */
export function SharedItemViewer({ resourceType, resourceId, onClose }: {
  resourceType: string; resourceId: string; onClose: () => void;
}) {
  const t = useT();
  const [status, setStatus] = useState<Status>("loading");
  const [view, setView] = useState<SharedResourceView | null>(null);

  useEffect(() => {
    let live = true;
    setStatus("loading");
    api.shares
      .view(resourceType, resourceId)
      .then((v) => { if (live) { setView(v); setStatus("ready"); } })
      .catch(() => { if (live) { setView(null); setStatus("gone"); } });
    return () => { live = false; };
  }, [resourceType, resourceId]);

  const r = view?.resource ?? {};
  const fields: Array<[string, string | null]> = resourceType === "story"
    ? [["title", text(r.title)], ["situation", text(r.situation)], ["task", text(r.task)], ["action", text(r.action)], ["result", text(r.result)]]
    : [["role", text(r.target_role)], ["score", text(r.overall_score)], ["summary", text(r.summary)]];
  const bullets = resourceType === "story"
    ? list(r.competencies)
    : [...list(r.strengths), ...list(r.focus_areas)];

  return (
    <Card data-testid="shared-item-viewer" role="region" aria-label={`${t(resourceTypeKey(resourceType))} #${resourceId}`}>
      <CardBody className="grid gap-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">{t(resourceTypeKey(resourceType))} #{resourceId}</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>{t("wsMgmt.hideShared")}</Button>
        </div>
        {status === "loading" && <p className="text-sm text-muted" role="status">{t("wsMgmt.viewerLoading")}</p>}
        {status === "gone" && <p className="text-sm text-muted" role="status">{t("wsMgmt.viewerUnavailable")}</p>}
        {status === "ready" && (
          <div className="grid gap-1 text-sm">
            {fields.filter(([, v]) => v).map(([k, v]) => <p key={k} className="whitespace-pre-wrap">{v}</p>)}
            {bullets.length > 0 && (
              <ul className="list-disc pl-5">{bullets.map((b, i) => <li key={`${i}-${b}`}>{b}</li>)}</ul>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
