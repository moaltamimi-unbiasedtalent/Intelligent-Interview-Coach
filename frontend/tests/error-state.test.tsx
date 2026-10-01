import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { translate } from "@/lib/i18n/catalog";
import { SUPPORTED_LOCALE_CODES } from "@/lib/i18n/locales";
import { stateKeyForError } from "@/lib/api/errors";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { ErrorState } from "@/components/ui/States";

/**
 * P10B-W9.7A - error presentation hierarchy. The semantics (what is shown, retried, classified) are the
 * W9.1/W9.2 ones and are NOT changed here; only the SIZE of the card now matches the severity:
 *   section  = compact inline note (one degraded region)
 *   page     = proportional recoverable card (default; no viewport-sized block)
 *   fatal    = the large centred treatment, reserved for the route error boundary.
 * Assertions are semantic/layout-class based (no brittle pixel snapshots); real geometry is asserted in E2E.
 */

const PAGE_BLOCKERS = ["py-10", "text-center", "py-12", "min-h-screen", "min-h-[60vh]", "h-screen"];

describe("ErrorState hierarchy", () => {
  it("1. section variant is compact (small padding, no heading, no centred block)", () => {
    render(<ErrorState variant="section" message="Section failed" onRetry={() => {}} />);
    const el = screen.getByRole("alert");
    expect(el.className).toContain("py-3");
    for (const c of PAGE_BLOCKERS) expect(el.className).not.toContain(c);
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("2. page (default) variant is proportional: bounded padding, left aligned, left danger accent", () => {
    render(<ErrorState message="Page failed" onRetry={() => {}} />);
    const el = screen.getByRole("alert");
    expect(el.getAttribute("data-error-variant")).toBe("page");
    expect(el.className).toContain("py-4");
    expect(el.className).toContain("border-l-danger");
    for (const c of PAGE_BLOCKERS) expect(el.className, `page card must not carry ${c}`).not.toContain(c);
    expect(screen.getByRole("heading", { name: translate("en", "states.somethingWentWrong") })).toBeInTheDocument();
  });

  it("2b. fatal variant keeps the large centred treatment (reserved for the route error boundary)", () => {
    render(<ErrorState variant="fatal" message="Crash" onRetry={() => {}} />);
    const el = screen.getByRole("alert");
    expect(el.className).toContain("py-10");
    expect(el.className).toContain("text-center");
  });
});

describe("ErrorState disclosure + retry", () => {
  it("3-5. Technical details is collapsed initially, opens on click, and shows the request id", async () => {
    const { container } = render(<ErrorState message="m" requestId="req_abc123" onRetry={() => {}} />);
    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    const summary = screen.getByText(translate("en", "states.technicalDetails"));
    expect(summary.tagName).toBe("SUMMARY");
    await userEvent.click(summary);
    expect(details.open).toBe(true);
    expect(screen.getByText(/req_abc123/)).toBeVisible();
    // (Keyboard Enter/Space toggling of <summary> is native browser behaviour that jsdom does not implement;
    // it is asserted in real Chromium in e2e/experience-closure.spec.ts.)
  });

  it("no disclosure when there is no request id (nothing to hide)", () => {
    const { container } = render(<ErrorState message="m" onRetry={() => {}} />);
    expect(container.querySelector("details")).toBeNull();
  });

  it("6. Retry invokes the handler once per activation, by click and by keyboard; busy state disables it", async () => {
    const onRetry = vi.fn();
    const { rerender } = render(<ErrorState message="m" onRetry={onRetry} />);
    const btn = screen.getByRole("button", { name: translate("en", "states.retry") });
    await userEvent.click(btn);
    btn.focus();
    await userEvent.keyboard("{Enter}");
    expect(onRetry).toHaveBeenCalledTimes(2);
    rerender(<ErrorState message="m" onRetry={onRetry} retrying />);
    const busy = screen.getByRole("button", { name: translate("en", "states.retrying") });
    expect(busy).toBeDisabled();
    expect(busy).toHaveAttribute("aria-busy", "true");
  });

  it("9 + focus: a successful Retry removes the error and moves focus to the main region (not <body>)", async () => {
    function Harness() {
      const [failed, setFailed] = useState(true);
      return (
        <main id="main" tabIndex={-1}>
          {failed ? <ErrorState message="m" requestId="r1" onRetry={() => setFailed(false)} /> : <p>content restored</p>}
        </main>
      );
    }
    render(<Harness />);
    const btn = screen.getByRole("button", { name: translate("en", "states.retry") });
    btn.focus();
    expect(document.activeElement).toBe(btn);
    await userEvent.click(btn);
    expect(screen.getByText("content restored")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(document.getElementById("main"));
  });

  it("alert semantics: one alert region; Retry has a visible keyboard focus ring", () => {
    render(<ErrorState message="m" requestId="r" onRetry={() => {}} />);
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("button", { name: translate("en", "states.retry") }).className).toContain("focus-visible:outline");
  });
});

describe("7/8. ErrorState chrome is localized in all 8 locales (incl. Russian), incl. every error kind", () => {
  const CHROME = ["states.somethingWentWrong", "states.retry", "states.technicalDetails", "states.reference"];
  const KINDS = ["offline", "unreachable", "unauthenticated", "forbidden", "notFound", "validation", "conflict",
    "rateLimited", "unavailable", "server", "unknown"] as const;

  for (const locale of SUPPORTED_LOCALE_CODES) {
    it(`${locale}: title, message, Retry, Technical details, Reference render in ${locale}`, () => {
      const message = translate(locale, stateKeyForError("server"));
      render(
        <I18nProvider initialLocale={locale}>
          <ErrorState message={message} requestId="req_xyz" onRetry={() => {}} />
        </I18nProvider>,
      );
      expect(screen.getByRole("heading", { name: translate(locale, "states.somethingWentWrong") })).toBeInTheDocument();
      expect(screen.getByText(message)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: translate(locale, "states.retry") })).toBeInTheDocument();
      expect(screen.getByText(translate(locale, "states.technicalDetails"))).toBeInTheDocument();
      expect(screen.getByText(new RegExp(translate(locale, "states.reference").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))).toBeInTheDocument();
    });

    it(`${locale}: every error kind has a localized message (non-English locales differ from English)`, () => {
      for (const kind of KINDS) {
        const key = stateKeyForError(kind);
        const text = translate(locale, key);
        expect(text.trim().length, `${locale} ${key}`).toBeGreaterThan(0);
        if (locale !== "en") expect(text, `${locale} ${key} must not be the English string`).not.toBe(translate("en", key));
      }
      if (locale !== "en") {
        for (const k of CHROME) expect(translate(locale, k), `${locale} ${k}`).not.toBe(translate("en", k));
      }
    });
  }

  it("8. Russian error copy is Cyrillic (title, Retry, Technical details)", () => {
    for (const k of ["states.somethingWentWrong", "states.retry", "states.technicalDetails"]) {
      expect(translate("ru", k)).toMatch(/[Ѐ-ӿ]/);
    }
  });
});
