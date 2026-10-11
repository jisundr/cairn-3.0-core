import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ACCENT_THEMES, applyAccentTheme, getStoredAccentTheme, setStoredAccentTheme } from "./theme";

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.accentTheme;
});

describe("applyAccentTheme", () => {
  it("sets data-accent-theme to a known preset id", () => {
    applyAccentTheme(ACCENT_THEMES[0].id);
    expect(document.documentElement.dataset.accentTheme).toBe(ACCENT_THEMES[0].id);
  });

  it("clears the attribute for null", () => {
    applyAccentTheme(ACCENT_THEMES[0].id);
    applyAccentTheme(null);
    expect(document.documentElement.dataset.accentTheme).toBeUndefined();
  });

  it("falls back to the default (attribute absent) for an unknown/stale id", () => {
    document.documentElement.dataset.accentTheme = "some-removed-preset";
    applyAccentTheme("some-removed-preset");
    expect(document.documentElement.dataset.accentTheme).toBeUndefined();
  });
});

describe("getStoredAccentTheme / setStoredAccentTheme", () => {
  it("round-trips a preset id through localStorage", () => {
    expect(getStoredAccentTheme()).toBeNull();
    setStoredAccentTheme(ACCENT_THEMES[1].id);
    expect(getStoredAccentTheme()).toBe(ACCENT_THEMES[1].id);
    expect(localStorage.getItem("mc-accent-theme")).toBe(ACCENT_THEMES[1].id);
  });

  it("removes the key rather than writing a sentinel when cleared", () => {
    setStoredAccentTheme(ACCENT_THEMES[1].id);
    setStoredAccentTheme(null);
    expect(getStoredAccentTheme()).toBeNull();
    expect(localStorage.getItem("mc-accent-theme")).toBeNull();
  });
});

describe("localStorage unavailable (private browsing, storage disabled)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("getStoredAccentTheme returns null instead of throwing", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => getStoredAccentTheme()).not.toThrow();
    expect(getStoredAccentTheme()).toBeNull();
  });

  it("setStoredAccentTheme doesn't throw when setting or clearing", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => setStoredAccentTheme(ACCENT_THEMES[0].id)).not.toThrow();
    expect(() => setStoredAccentTheme(null)).not.toThrow();
  });
});
