import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/components/i18n/I18nProvider";
import { Logo } from "@/components/ui/Logo";
import { Brand } from "@/components/layout/Brand";
import { LanguageMenu } from "@/components/i18n/LanguageMenu";
import { DictationControl } from "@/components/ui/DictationControl";
import { FakeSpeechAdapter } from "./_fakeSpeech";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/app",
  useSearchParams: () => new URLSearchParams(),
}));

function wrap(ui: React.ReactNode, locale: "en" | "de" = "en") {
  return render(<I18nProvider initialLocale={locale}>{ui}</I18nProvider>);
}

afterEach(() => vi.restoreAllMocks());

describe("Wave 1 — canonical brand", () => {
  it("Logo uses the vector mark (no emoji) and is an accessible home link", () => {
    wrap(<Logo href="/app" />);
    const link = screen.getByRole("link", { name: "Ask4Mo - home" });
    expect(link).toHaveAttribute("href", "/app");
    const img = link.querySelector("img");
    expect(img).toHaveAttribute("src", "/brand/ask4mo-mark.svg");
    // No emoji substitute anywhere in the brand lockup.
    expect(link.textContent).not.toMatch(/[🎯📚🧠🚀]/u);
  });

  it("app Brand links to /app via the shared Logo", () => {
    wrap(<Brand />);
    expect(screen.getByRole("link", { name: "Ask4Mo - home" })).toHaveAttribute("href", "/app");
  });
});

describe("Wave 1 — global language menu", () => {
  it("offers all seven locales and switches on select", async () => {
    wrap(<LanguageMenu />);
    const button = screen.getByTestId("language-menu-button");
    await userEvent.click(button);
    // Native labels for the seven supported locales.
    for (const label of ["English", "Deutsch", "Français", "Español", "Italiano", "Português", "Nederlands"]) {
      expect(screen.getByRole("menuitemradio", { name: new RegExp(label) })).toBeInTheDocument();
    }
    // Selecting German switches the current locale indicator.
    await userEvent.click(screen.getByRole("menuitemradio", { name: /Deutsch/ }));
    expect(screen.getByTestId("language-menu-button")).toHaveTextContent(/de/i);
  });
});

describe("Wave 1 — dictation discoverability", () => {
  it("shows an accessible hint (not silent null) when unsupported", () => {
    const adapter = new FakeSpeechAdapter();
    // Force unsupported.
    vi.spyOn(adapter, "isSupported").mockReturnValue(false);
    wrap(<DictationControl value="" onChange={() => {}} adapter={adapter} />);
    const note = screen.getByTestId("dictation-unsupported");
    expect(note).toBeInTheDocument();
    expect(note.textContent).toMatch(/type instead/i);
  });

  it("renders the mic control (not the hint) when supported", () => {
    const adapter = new FakeSpeechAdapter();
    wrap(<DictationControl value="" onChange={() => {}} adapter={adapter} />);
    expect(screen.queryByTestId("dictation-unsupported")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /dictation/i })).toBeInTheDocument();
  });
});
