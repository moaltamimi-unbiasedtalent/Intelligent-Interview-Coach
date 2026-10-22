import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationLanguageField } from "@/components/i18n/ConversationLanguageField";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { LanguageMenu } from "@/components/i18n/LanguageMenu";
import { api } from "@/lib/api/client";
import { offeredLocalesFrom, resetOfferedLocalesCache } from "@/lib/i18n/offeredLocales";

const SEVEN = ["en", "de", "fr", "es", "it", "pt", "nl"];

function serve(caps: Record<string, unknown>) {
  vi.spyOn(api, "capabilities").mockResolvedValue(caps as never);
}

beforeEach(() => resetOfferedLocalesCache());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** 06H (REQ-LANG-11/13/14): the selectors reflect the server's activation decision; the server enforces it again on every new activity. */
describe("06H offered locales projection", () => {
  it("keeps the static seven, unlabelled, while the server answer is unknown", () => {
    const r = offeredLocalesFrom(undefined);
    expect(r.known).toBe(false);
    expect(r.options.map((o) => o.code)).toEqual(SEVEN);
    expect(r.options.some((o) => o.unqualified)).toBe(false);
    expect(r.noneAvailable).toBe(false);
  });

  it("labels the unqualified locales in development and test", () => {
    const r = offeredLocalesFrom({ active_candidate_locales: SEVEN, unqualified_locales: SEVEN });
    expect(r.known).toBe(true);
    expect(r.options.every((o) => o.unqualified)).toBe(true);
  });

  it("offers only the qualified subset in a hosted environment and never a locale the server did not offer", () => {
    const r = offeredLocalesFrom({ active_candidate_locales: ["de", "ru", "xx"], unqualified_locales: [] });
    expect(r.options.map((o) => o.code)).toEqual(["de"]); // ru is not selectable; unknown codes are ignored
  });

  it("an explicit empty list means no language is available (fail closed, no implicit English)", () => {
    const r = offeredLocalesFrom({ active_candidate_locales: [], unqualified_locales: [] });
    expect(r.known).toBe(true);
    expect(r.options).toEqual([]);
    expect(r.noneAvailable).toBe(true);
  });
});

describe("06H selectors", () => {
  it("the conversation field hides locales the server did not offer in hosted mode", async () => {
    serve({ active_candidate_locales: ["de"], unqualified_locales: [], qualified_locales: ["de"] });
    render(
      <I18nProvider initialLocale="en">
        <ConversationLanguageField value="de" onChange={() => {}} />
      </I18nProvider>,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    await waitFor(() => expect(Array.from(select.options).map((o) => o.value)).toEqual(["de"]));
    expect(screen.queryByTestId("language-none-available")).toBeNull();
  });

  it("the conversation field labels unqualified languages in development", async () => {
    serve({ active_candidate_locales: SEVEN, unqualified_locales: SEVEN });
    render(
      <I18nProvider initialLocale="en">
        <ConversationLanguageField value="en" onChange={() => {}} />
      </I18nProvider>,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    await waitFor(() => expect(select.options[0].textContent).toContain("(Unqualified)"));
    expect(select.options).toHaveLength(7);
  });

  it("shows a disabled selector and a clear unavailable state when no language is qualified", async () => {
    serve({ active_candidate_locales: [], unqualified_locales: [], no_language_available: true });
    render(
      <I18nProvider initialLocale="en">
        <ConversationLanguageField value="en" onChange={() => {}} />
      </I18nProvider>,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    await waitFor(() => expect(screen.getByTestId("language-none-available")).toBeTruthy());
    expect(select.disabled).toBe(true);
    expect(select.options).toHaveLength(0);
  });

  it("the header menu lists only offered languages and labels unqualified ones", async () => {
    serve({ active_candidate_locales: ["de", "fr"], unqualified_locales: ["fr"] });
    const user = userEvent.setup();
    render(
      <I18nProvider initialLocale="en">
        <LanguageMenu />
      </I18nProvider>,
    );
    await waitFor(() => expect(api.capabilities).toHaveBeenCalled());
    await user.click(screen.getByTestId("language-menu-button"));
    await waitFor(() => expect(screen.getAllByRole("menuitemradio")).toHaveLength(2));
    expect(screen.getByTestId("language-unqualified-fr")).toBeTruthy();
    expect(screen.queryByTestId("language-unqualified-de")).toBeNull();
  });

  it("the header menu shows no choices and the unavailable note when the server offers nothing", async () => {
    serve({ active_candidate_locales: [], unqualified_locales: [] });
    const user = userEvent.setup();
    render(
      <I18nProvider initialLocale="en">
        <LanguageMenu />
      </I18nProvider>,
    );
    await waitFor(() => expect(api.capabilities).toHaveBeenCalled());
    await user.click(screen.getByTestId("language-menu-button"));
    await waitFor(() => expect(screen.getByTestId("language-none-available")).toBeTruthy());
    expect(screen.queryAllByRole("menuitemradio")).toHaveLength(0);
  });

  it("falls back to the static seven when capabilities cannot be fetched", async () => {
    vi.spyOn(api, "capabilities").mockRejectedValue(new Error("offline"));
    render(
      <I18nProvider initialLocale="en">
        <ConversationLanguageField value="en" onChange={() => {}} />
      </I18nProvider>,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    await waitFor(() => expect(api.capabilities).toHaveBeenCalled());
    expect(select.options).toHaveLength(7);
  });
});
