import { useState } from "react";
import { ACCENT_THEMES, applyAccentTheme, getStoredAccentTheme, setStoredAccentTheme } from "../lib/theme";

// Per-install accent picker (see ../../REQUIREMENTS.md) - reuses the same
// .dropdown-wrap/.dropdown-btn/.dropdown-menu/.dropdown-item markup and
// open/close useState pattern AppHeader's own nav-dropdown and
// InstallScopeRow's install-scope dropdown already use, rather than a third
// bespoke implementation. Deliberately takes no props: it reads/writes
// localStorage and the DOM attribute directly, which is what keeps the
// accent independent of AppHeader's own props (activeTab, connected, etc.)
// and of whatever project the board/Overview filter currently has selected.
export function AccentPicker() {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(() => getStoredAccentTheme());

  return (
    <div className="dropdown-wrap">
      <button
        type="button"
        className="dropdown-btn"
        data-testid="accent-picker-btn"
        aria-label="Accent theme"
        onClick={() => setOpen((o) => !o)}
      >
        {/* Trigger swatch reads --add directly (not a hex from theme.ts) so
            it always shows whatever's currently applied - the default green
            when no preset is picked, no separate "default" hex to keep in
            sync in JS. */}
        <span className="status-dot" aria-hidden="true" />
        Accent
        <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="dropdown-menu" data-testid="accent-picker-menu">
          {ACCENT_THEMES.map((theme) => (
            <div
              key={theme.id}
              className="dropdown-item"
              data-testid={`accent-picker-option-${theme.id}`}
              onClick={() => {
                setStoredAccentTheme(theme.id);
                applyAccentTheme(theme.id);
                setSelected(theme.id);
                setOpen(false);
              }}
            >
              <span
                className="status-dot"
                aria-hidden="true"
                style={{ background: theme.swatch, marginRight: 6, verticalAlign: "middle" }}
              />
              <span
                style={selected === theme.id ? { color: "var(--add)", fontWeight: 600 } : undefined}
              >
                {theme.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
