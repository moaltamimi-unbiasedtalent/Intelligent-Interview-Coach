import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/components/i18n/I18nProvider";
import { StoryCard } from "@/components/stories/StoryCard";
import { translate } from "@/lib/i18n/catalog";
import type { StoryOut } from "@/lib/api/types";

const remove = vi.fn().mockResolvedValue(undefined);
vi.mock("@/lib/api/client", () => ({ api: { stories: { remove: (...args: unknown[]) => remove(...args) } } }));

const story = (id: number, title: string): StoryOut => ({
  id, title, competencies: [], status: "user_created", evidence_state: "none", evidence_claim_ids: [],
});

describe("story deletion confirmation", () => {
  it.each(["en", "fr"] as const)("identifies only the selected story and retains the warning in %s", async (locale) => {
    const onDeleted = vi.fn();
    render(<I18nProvider initialLocale={locale}><ul>{[story(1, "First synthetic story"), story(2, "Second synthetic story")].map((s) => <StoryCard key={s.id} story={s} opportunities={[]} onChanged={vi.fn()} onEdit={vi.fn()} onDeleted={onDeleted} />)}</ul></I18nProvider>);
    await userEvent.click(within(screen.getByTestId("story-2")).getByRole("button", { name: translate(locale, "storyBank.delete") }));
    const dialog = screen.getByRole("alertdialog", { name: `${translate(locale, "storyBank.deleteTitle")} Second synthetic story` });
    expect(dialog).toHaveAccessibleDescription(translate(locale, "storyBank.deleteBody"));
    expect(within(dialog).queryByText("First synthetic story")).not.toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const cancel = within(dialog).getAllByRole("button")[0];
    expect(cancel).toHaveFocus();
    await userEvent.click(cancel);
    expect(remove).not.toHaveBeenCalled();
    await userEvent.click(within(screen.getByTestId("story-2")).getByRole("button", { name: translate(locale, "storyBank.delete") }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: translate(locale, "storyBank.delete") }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(2));
    expect(remove).toHaveBeenCalledWith(2);
    remove.mockClear();
  });
});
