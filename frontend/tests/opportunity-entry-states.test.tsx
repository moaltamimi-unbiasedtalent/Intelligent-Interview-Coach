import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";

/**
 * P10B-W9.7A - the Home Opportunity action must NEVER be an unlabeled blank rectangle.
 * Root cause: the old component rendered an `aria-hidden` pulsing placeholder whenever `count === null`,
 * and `count` was reset to null (never resolved) whenever auth was not "authenticated" - including
 * "unknown" (a failed /auth/me). A backend fault therefore left the placeholder on screen permanently.
 */

const list = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { opportunities: { list: (...a: unknown[]) => list(...a) } } }));

let auth: { status: string } | null = { status: "authenticated" };
vi.mock("@/components/auth/AuthProvider", () => ({ useAuthOptional: () => auth }));

import { OpportunityEntry } from "@/components/home/OpportunityEntry";
import { I18nProvider } from "@/components/i18n/I18nProvider";

beforeEach(() => {
  auth = { status: "authenticated" };
  list.mockReset();
});
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

const create = /create an opportunity/i;

describe("OpportunityEntry state machine (no permanent / blank placeholder)", () => {
  it("auth FAILED (unknown): shows the safe default create action immediately, no placeholder", () => {
    auth = { status: "unknown" };
    render(<OpportunityEntry />);
    expect(screen.getByRole("link", { name: create })).toHaveAttribute("href", "/opportunities?create=1");
    expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeNull();
    expect(list).not.toHaveBeenCalled();
  });

  it("unauthenticated: default create action (no placeholder)", () => {
    auth = { status: "unauthenticated" };
    render(<OpportunityEntry />);
    expect(screen.getByRole("link", { name: create })).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });

  it("auth still loading: a LABELLED status placeholder (not an unlabeled blank control)", () => {
    auth = { status: "loading" };
    render(<OpportunityEntry />);
    const loading = screen.getByTestId("opportunity-entry-loading");
    expect(loading).toHaveAttribute("role", "status");
    expect(loading).toHaveTextContent(translate("en", "states.loading"));
    expect(screen.queryByRole("link", { name: create })).not.toBeInTheDocument(); // no wrong early CTA
  });

  it("authenticated + list request pending: labelled placeholder, then resolves to the action", async () => {
    let resolve!: (v: unknown) => void;
    list.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<OpportunityEntry />);
    expect(screen.getByTestId("opportunity-entry-loading")).toBeInTheDocument();
    await act(async () => resolve({ opportunities: [] }));
    expect(await screen.findByRole("link", { name: create })).toBeInTheDocument();
    expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument();
  });

  it("authenticated + list request REJECTS: safe default action (W9.1 best-effort), placeholder gone", async () => {
    list.mockRejectedValue(new Error("boom"));
    render(<OpportunityEntry />);
    expect(await screen.findByRole("link", { name: create })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument());
  });

  it("authenticated + list request HANGS: the placeholder is bounded and gives up to the default action", async () => {
    vi.useFakeTimers();
    list.mockReturnValue(new Promise(() => {})); // never settles
    render(<OpportunityEntry />);
    expect(screen.getByTestId("opportunity-entry-loading")).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(4100);
    });
    expect(screen.getByRole("link", { name: create })).toBeInTheDocument();
    expect(screen.queryByTestId("opportunity-entry-loading")).not.toBeInTheDocument();
  });

  it("the action is a real link with a visible label and keyboard-focusable in every locale", async () => {
    auth = { status: "unknown" };
    for (const locale of SUPPORTED_LOCALE_CODES) {
      const { unmount } = render(
        <I18nProvider initialLocale={locale}>
          <OpportunityEntry />
        </I18nProvider>,
      );
      const label = translate(locale, "home.opportunityCreate");
      expect(label.trim().length).toBeGreaterThan(0);
      const link = screen.getByRole("link", { name: label });
      expect((link.textContent ?? "").trim()).toBe(label);
      link.focus();
      expect(document.activeElement).toBe(link);
      expect(link.className).toContain("focus-visible:outline"); // visible keyboard focus ring
      unmount();
    }
  });
});
