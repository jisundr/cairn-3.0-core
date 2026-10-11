import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ACCENT_THEMES } from "../lib/theme";
import { AccentPicker } from "./AccentPicker";

describe("AccentPicker", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.accentTheme;
  });

  it("renders every configured preset as a menu option", () => {
    render(<AccentPicker />);
    fireEvent.click(screen.getByTestId("accent-picker-btn"));

    for (const theme of ACCENT_THEMES) {
      expect(screen.getByTestId(`accent-picker-option-${theme.id}`)).toHaveTextContent(theme.label);
    }
  });

  it("persists the pick to localStorage and applies the DOM attribute when an option is clicked", () => {
    render(<AccentPicker />);
    fireEvent.click(screen.getByTestId("accent-picker-btn"));

    const target = ACCENT_THEMES[1];
    fireEvent.click(screen.getByTestId(`accent-picker-option-${target.id}`));

    expect(localStorage.getItem("mc-accent-theme")).toBe(target.id);
    expect(document.documentElement.dataset.accentTheme).toBe(target.id);
  });

  it("starts already marked selected when a preset is already in localStorage", () => {
    const preset = ACCENT_THEMES[2];
    localStorage.setItem("mc-accent-theme", preset.id);
    render(<AccentPicker />);
    fireEvent.click(screen.getByTestId("accent-picker-btn"));

    const option = screen.getByTestId(`accent-picker-option-${preset.id}`);
    const label = option.querySelector("span:last-child");
    expect(label).toHaveStyle({ fontWeight: "600" });
  });
});
