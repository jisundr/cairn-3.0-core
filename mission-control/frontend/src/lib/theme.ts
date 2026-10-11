// Per-install accent-theme presets (see design.css's
// `:root[data-accent-theme]` blocks for the full light+dark --add/--add-bg/
// --add-line sets - this module only knows each preset's id, label, and a
// light-mode swatch hex for rendering the picker itself). Each install
// (its own server.py process, its own browser origin) persists its pick to
// localStorage, so several simultaneously-open tabs read as distinct at a
// glance without any server-side change - see ../../REQUIREMENTS.md.

export interface AccentTheme {
  id: string;
  label: string;
  swatch: string; // light-mode --add hex, for the picker's own swatches
}

export const ACCENT_THEMES: AccentTheme[] = [
  { id: "blue", label: "Blue", swatch: "#2b6cc4" },
  { id: "purple", label: "Purple", swatch: "#7245c2" },
  { id: "pink", label: "Pink", swatch: "#c23b7a" },
  { id: "teal", label: "Teal", swatch: "#158f8a" },
  { id: "amber", label: "Amber", swatch: "#b8760f" },
];

const ACCENT_THEME_STORAGE_KEY = "mc-accent-theme";

function isKnownAccentTheme(id: string): boolean {
  return ACCENT_THEMES.some((t) => t.id === id);
}

export function getStoredAccentTheme(): string | null {
  try {
    return localStorage.getItem(ACCENT_THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredAccentTheme(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACCENT_THEME_STORAGE_KEY, id);
    else localStorage.removeItem(ACCENT_THEME_STORAGE_KEY);
  } catch {
    // localStorage unavailable (private browsing, etc.) - the pick just
    // won't persist across reloads; not worth failing the click over.
  }
}

// Sets/clears the DOM attribute design.css's preset blocks select on.
// A stale localStorage value from a since-removed preset (or any other
// unknown/null id) falls back to the default (attribute absent), never to
// rendering with no --add at all.
export function applyAccentTheme(id: string | null): void {
  if (id && isKnownAccentTheme(id)) {
    document.documentElement.dataset.accentTheme = id;
  } else {
    delete document.documentElement.dataset.accentTheme;
  }
}
