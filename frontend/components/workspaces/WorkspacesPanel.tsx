"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "@/components/i18n/I18nProvider";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api } from "@/lib/api/client";
import type { MyWorkspaces, ShareGrantOut } from "@/lib/api/types";

export function WorkspacesPanel() {
  const t = useT();
  const [data, setData] = useState<MyWorkspaces | null>(null);
  const [sharedByMe, setSharedByMe] = useState<ShareGrantOut[]>([]);
  const [sharedWithMe, setSharedWithMe] = useState<ShareGrantOut[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [ws, mine, withMe] = await Promise.all([
        api.workspaces.list(),
        api.shares.mine(),
        api.shares.withMe(),
      ]);
      setData(ws);
      setSharedByMe(mine.shares);
      setSharedWithMe(withMe.shares);
      setStatus("ready");
    } catch {
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Accept flow: if arriving from an invitation email link (?token=...), accept it.
    const token = new URLSearchParams(window.location.search).get("token");
    if (token) {
      api.workspaces
        .accept(token)
        .then(() => {
          setNotice("Invitation accepted.");
          void refresh();
        })
        .catch(() => setNotice("That invitation could not be accepted (it may be expired or for a different email)."));
    }
  }, [refresh]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.workspaces.create(name.trim());
      setName("");
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const leave = async (id: number) => {
    setBusy(true);
    try {
      await api.workspaces.leave(id);
      await refresh();
    } catch {
      setNotice("You cannot leave as the last owner — transfer ownership first.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (shareId: number) => {
    setBusy(true);
    try {
      await api.shares.revoke(shareId);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  if (status === "loading") return <p className="text-sm text-muted">{t("states.loading")}…</p>;
  if (status === "error") return <p className="text-sm text-muted">{t("states.genericError")}</p>;

  return (
    <div className="grid gap-4">
      <Card>
        <CardBody className="grid gap-2">
          <p className="text-sm text-muted">{t("workspaces.privacyNote")}</p>
          {notice && <p className="text-sm text-accent">{notice}</p>}
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border border-default bg-transparent px-3 py-2 text-sm"
              placeholder={t("workspaces.namePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label={t("workspaces.namePlaceholder")}
            />
            <Button onClick={create} disabled={busy || !name.trim()}>{t("workspaces.create")}</Button>
          </div>
        </CardBody>
      </Card>

      <section className="grid gap-2">
        <h2 className="text-base font-semibold">{t("workspaces.myWorkspaces")}</h2>
        {data && data.workspaces.length === 0 && (
          <p className="text-sm text-muted">{t("workspaces.emptyWorkspaces")}</p>
        )}
        {data?.workspaces.map((w) => (
          <Card key={w.id}>
            <CardBody className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium">{w.name}</p>
                <p className="text-xs text-muted">
                  {w.my_role === "workspace_owner" ? t("workspaces.owner") : t("workspaces.member")}
                  {" · "}
                  {w.member_count} {t("workspaces.members")}
                </p>
              </div>
              <Button variant="ghost" onClick={() => leave(w.id)} disabled={busy}>{t("workspaces.leave")}</Button>
            </CardBody>
          </Card>
        ))}
      </section>

      {data && data.invited.length > 0 && (
        <section className="grid gap-2">
          <h2 className="text-base font-semibold">{t("workspaces.invited")}</h2>
          {data.invited.map((inv) => (
            <Card key={inv.id}>
              <CardBody>
                <p className="text-sm">{inv.workspace_name ?? `#${inv.workspace_id}`}</p>
                <p className="text-xs text-muted">{t("workspaces.accept")} — check your email link.</p>
              </CardBody>
            </Card>
          ))}
        </section>
      )}

      <section className="grid gap-2">
        <h2 className="text-base font-semibold">{t("workspaces.sharedByMe")}</h2>
        {sharedByMe.length === 0 && <p className="text-sm text-muted">{t("workspaces.emptyShares")}</p>}
        {sharedByMe.map((s) => (
          <Card key={s.id}>
            <CardBody className="flex items-center justify-between gap-3">
              <p className="text-sm">{s.resource_type} #{s.resource_id}</p>
              <Button variant="ghost" onClick={() => revoke(s.id)} disabled={busy}>{t("workspaces.revoke")}</Button>
            </CardBody>
          </Card>
        ))}
      </section>

      <section className="grid gap-2">
        <h2 className="text-base font-semibold">{t("workspaces.sharedWithMe")}</h2>
        {sharedWithMe.length === 0 && <p className="text-sm text-muted">{t("workspaces.emptyShares")}</p>}
        {sharedWithMe.map((s) => (
          <Card key={s.id}>
            <CardBody>
              <p className="text-sm">{s.resource_type} #{s.resource_id}</p>
            </CardBody>
          </Card>
        ))}
      </section>
    </div>
  );
}
