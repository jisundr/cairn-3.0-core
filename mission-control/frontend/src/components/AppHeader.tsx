import { useEffect, useRef, useState } from "react";
import { useTasks } from "../api/hooks";
import {
  armChimeOnFirstInteraction,
  isChimeArmed,
  isMuted,
  needsAttentionCount,
  newAttentionKeys,
  setMuted,
  titleForCount,
  updateFavicon,
} from "../lib/attention";
import { AccentPicker } from "./AccentPicker";
import { RefreshIcon, VolumeIcon } from "./icons";

// Header block per `overview-loaded.html`'s `header.app` markup - shared by
// every tab-bar screen (Overview, Sessions List). The Session Drilldown
// screen replaces this entirely with its own `.drill-header` (App.tsx never
// mounts this component while a session is open). `showTabs`/`onRefresh`/
// `updatedLabel`/`refreshing` are each independently optional because the mockups don't
// render the same right-hand cluster on every screen: overview-empty.html
// keeps the nav but drops refresh/updated-at; overview-disconnected.html
// drops the nav entirely too; sessions-list-*.html keeps refresh but never
// shows updated-at. The hostname (F2) moved out of here onto its own
// `InstallScopeRow` - this header no longer takes or renders it.
//
// F3: below design.css's existing 900px breakpoint, `nav.app-tabs` and the
// wordmark's " mission-control" suffix hide and a `.dropdown-btn.nav-
// dropdown` (labeled with the active tab) takes over navigating between
// the same two tabs - CSS-only for which one is visible, both always
// rendered so no JS breakpoint check duplicates that logic.
export type AppTab = "overview" | "sessions" | "kanban";

// F3's collapsed-nav dropdown showed only "the other tab" back when there
// were exactly two; a 3rd tab needs the full list minus whichever is active,
// not a single swap target.
const ALL_TABS: AppTab[] = ["overview", "sessions", "kanban"];
const TAB_LABEL: Record<AppTab, string> = { overview: "Overview", sessions: "Sessions", kanban: "Kanban" };
const TAB_PATH: Record<AppTab, string> = { overview: "/", sessions: "/sessions", kanban: "/kanban" };

interface AppHeaderProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  connected: boolean;
  showTabs?: boolean;
  onRefresh?: () => void;
  updatedLabel?: string | null;
  // True while a click-triggered refresh is in flight: the refresh button
  // spins and is disabled. Pages that omit it are unchanged.
  refreshing?: boolean;
}

export function AppHeader({
  activeTab,
  onTabChange,
  connected,
  showTabs = true,
  onRefresh,
  updatedLabel,
  refreshing,
}: AppHeaderProps) {
  const [navOpen, setNavOpen] = useState(false);
  const [muted, setMutedState] = useState(() => isMuted());
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Cross-project, unfiltered - this is the same aggregate the Kanban board
  // itself shows before any project filter narrows it (PRD §9's "matches
  // the board's own column count"), and the one count this pill/title/
  // favicon show from every tab, not just Kanban. React Query dedupes this
  // against Kanban's own identical, unfiltered call under the same
  // queryKey, so no extra polling for a page that mounts both.
  const tasks = useTasks();
  const attentionCount = needsAttentionCount(tasks.data);

  useEffect(() => {
    armChimeOnFirstInteraction();
  }, []);

  useEffect(() => {
    document.title = titleForCount(attentionCount);
  }, [attentionCount]);

  useEffect(() => {
    updateFavicon(attentionCount > 0);
  }, [attentionCount]);

  // Diffs every poll's Needs Attention set against the previous one
  // (`lib/attention.ts`'s module-level state, since this component itself
  // remounts on every tab switch) - chimes only for a folder newly entering
  // the set, only once armed by a first click and not explicitly muted.
  useEffect(() => {
    const newKeys = newAttentionKeys(tasks.data);
    if (newKeys.length === 0 || !isChimeArmed() || muted) return;
    if (!audioRef.current) audioRef.current = new Audio("/attention.wav");
    audioRef.current.currentTime = 0;
    void audioRef.current.play().catch(() => {});
  }, [tasks.data, muted]);

  return (
    <header className="app">
      <div className="app-left">
        <span className="wordmark">
          <span className="dim">~/ </span>cairn<span className="sep">/</span>
          <span className="sub">mission-control</span>
          <span className="sub-short">mc</span>
        </span>
        {showTabs && (
          <>
            <nav className="app-tabs">
              {ALL_TABS.map((tab) => (
                <a
                  key={tab}
                  href={TAB_PATH[tab]}
                  className={activeTab === tab ? "active" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    onTabChange(tab);
                  }}
                >
                  {TAB_LABEL[tab]}
                </a>
              ))}
            </nav>
            <div className="dropdown-wrap">
              <button
                type="button"
                className="dropdown-btn nav-dropdown"
                data-testid="nav-dropdown"
                onClick={() => setNavOpen((o) => !o)}
              >
                {TAB_LABEL[activeTab]}
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {navOpen && (
                <div className="dropdown-menu" data-testid="nav-dropdown-menu">
                  {ALL_TABS.filter((tab) => tab !== activeTab).map((tab) => (
                    <div
                      key={tab}
                      className="dropdown-item"
                      data-testid={`nav-dropdown-option-${tab}`}
                      onClick={() => {
                        onTabChange(tab);
                        setNavOpen(false);
                      }}
                    >
                      {TAB_LABEL[tab]}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
      <div className="app-right">
        <AccentPicker />
        {attentionCount > 0 && (
          <button
            type="button"
            className="attn-pill"
            data-testid="attention-pill"
            onClick={() => onTabChange("kanban")}
          >
            {attentionCount} need attention
          </button>
        )}
        <button
          type="button"
          className="icon-btn"
          title={muted ? "Unmute attention chime" : "Mute attention chime"}
          aria-label={muted ? "Unmute attention chime" : "Mute attention chime"}
          data-testid="attention-mute-toggle"
          onClick={() => {
            const next = !muted;
            setMuted(next);
            setMutedState(next);
          }}
        >
          <VolumeIcon muted={muted} />
        </button>
        <span
          className={connected ? "status-dot" : "status-dot err"}
          title={connected ? "Connected to the local server" : "Can't reach the local server"}
        />
        {onRefresh && (
          <button
            className={refreshing ? "icon-btn spinning" : "icon-btn"}
            title="Refresh now"
            aria-label="Refresh now"
            aria-busy={refreshing}
            disabled={refreshing}
            onClick={onRefresh}
          >
            <RefreshIcon />
          </button>
        )}
        {updatedLabel && <span className="updated-at mono">{updatedLabel}</span>}
      </div>
    </header>
  );
}
