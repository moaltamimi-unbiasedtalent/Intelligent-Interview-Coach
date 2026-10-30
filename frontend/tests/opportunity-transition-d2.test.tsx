import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ list: vi.fn(), locale: "fr" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: any) => <a href={href} {...props}>{children}</a> }));
vi.mock("@/lib/api/client", () => ({ api: { opportunities: { list: (...args: unknown[]) => state.list(...args) } } }));
vi.mock("@/components/i18n/I18nProvider", () => {
  const fr = (key: string) => `fr:${key}`, en = (key: string) => `en:${key}`;
  return { useI18n: () => ({ t: state.locale === "fr" ? fr : en }), useT: () => state.locale === "fr" ? fr : en };
});
vi.mock("@/components/opportunities/OpportunityCreate", () => ({ OpportunityCreate: ({ onCreated }: { onCreated: (id: number) => void }) => <button onClick={() => onCreated(7)}>synthetic-create</button> }));
import { OpportunitiesClient } from "@/components/opportunities/OpportunitiesClient";

const item = { id: 7, title: "Synthetic role - Synthetic company", target_role: "Synthetic role", company_name: "Synthetic company", status: "active" };
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
afterEach(() => { cleanup(); state.list.mockReset(); state.locale = "fr"; window.history.replaceState(null, "", "/"); });

it("consumes only the create intent after success and keeps it consumed on remount", async () => {
  window.history.replaceState(null, "", "/opportunities?create=1&filter=all#content");
  state.list.mockResolvedValue({ opportunities: [item] });
  const view = render(<OpportunitiesClient />);
  await userEvent.click(screen.getByText("synthetic-create"));
  expect(await screen.findByRole("link", { name: /Synthetic role - Synthetic company/ })).toHaveAttribute("href", "/opportunities/7");
  expect(window.location.search).toBe("?filter=all"); expect(window.location.hash).toBe("#content");
  view.unmount(); render(<OpportunitiesClient />);
  expect(await screen.findByRole("link", { name: /Synthetic role - Synthetic company/ })).toBeVisible();
  expect(screen.queryByText("synthetic-create")).toBeNull();
});

it.each(["empty", "error"] as const)("ignores an older %s response after the newer list is visible", async (outcome) => {
  window.history.replaceState(null, "", "/opportunities?create=1");
  const old = deferred<{ opportunities: unknown[] }>(), latest = deferred<{ opportunities: unknown[] }>();
  state.list.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise);
  render(<OpportunitiesClient />); await userEvent.click(screen.getByText("synthetic-create"));
  await act(async () => { latest.resolve({ opportunities: [item] }); await latest.promise; });
  const link = await screen.findByRole("link", { name: /Synthetic role - Synthetic company/ });
  await act(async () => { if (outcome === "empty") old.resolve({ opportunities: [] }); else old.reject(new Error("synthetic failure")); await old.promise.catch(() => undefined); });
  expect(link).toBeVisible(); expect(link).toHaveAttribute("href", "/opportunities/7");
});

it("keeps the created list visible when locale changes", async () => {
  window.history.replaceState(null, "", "/opportunities?create=1");
  state.list.mockResolvedValue({ opportunities: [item] });
  const view = render(<OpportunitiesClient />); await userEvent.click(screen.getByText("synthetic-create"));
  expect(await screen.findByRole("link", { name: /Synthetic role - Synthetic company/ })).toBeVisible();
  state.locale = "en"; view.rerender(<OpportunitiesClient />);
  expect(await screen.findByRole("link", { name: /Synthetic role - Synthetic company/ })).toBeVisible();
  expect(screen.queryByText("synthetic-create")).toBeNull();
});
