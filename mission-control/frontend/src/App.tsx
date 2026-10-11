import { useEffect, useState } from "react";
import type { AppTab } from "./components/AppHeader";
import { Drilldown } from "./pages/Drilldown";
import { Kanban } from "./pages/Kanban";
import { Overview } from "./pages/Overview";
import { SessionsList } from "./pages/SessionsList";

type DrawerTab = "details" | "docs";
type View =
  | { kind: "tab"; tab: AppTab; task?: string; drawerTab?: DrawerTab; boardProject?: string }
  | { kind: "session"; sessionId: string };

function pathForView(view: View): string {
  if (view.kind === "session") return `/sessions/${encodeURIComponent(view.sessionId)}`;
  if (view.tab === "sessions") return "/sessions";
  if (view.tab === "kanban") {
    // Drawer URL state (PRD §6.5): `?task=<folder>&tab=details|docs`, shareable
    // and restorable on a hard reload - the query string lives only on the
    // Kanban path, the other tabs' own URLs are untouched by this feature.
    // `project` is the board's own visible filter (distinct from the
    // drawer's `openTaskProject`, which is intentionally never in the URL
    // per §6.5) - it round-trips the same way, alone or alongside task/tab.
    const params = new URLSearchParams();
    if (view.task) {
      params.set("task", view.task);
      params.set("tab", view.drawerTab ?? "details");
    }
    if (view.boardProject) params.set("project", view.boardProject);
    const query = params.toString();
    return query ? `/kanban?${query}` : "/kanban";
  }
  return "/";
}

function parseView(pathname: string, search: string): View {
  const sessionMatch = pathname.match(/^\/sessions\/(.+)$/);
  if (sessionMatch) return { kind: "session", sessionId: decodeURIComponent(sessionMatch[1]) };
  if (pathname.startsWith("/kanban")) {
    const params = new URLSearchParams(search);
    const task = params.get("task") ?? undefined;
    const drawerTab: DrawerTab = params.get("tab") === "docs" ? "docs" : "details";
    const boardProject = params.get("project") ?? undefined;
    return { kind: "tab", tab: "kanban", task, drawerTab, boardProject };
  }
  return { kind: "tab", tab: pathname.startsWith("/sessions") ? "sessions" : "overview" };
}

// Path-based nav, no router library - ported from token-metering/frontend's
// Dashboard.tsx approach, so a hard reload of /sessions or /sessions/<id>
// lands back on the same view instead of resetting to Overview. Each page
// owns its own `.shell` + header (their header props differ too much
// across states - e.g. Overview/Disconnected drops the nav entirely - to
// hoist into one shared wrapper here).
export function App() {
  const initialView = parseView(window.location.pathname, window.location.search);
  const [activeTab, setActiveTabState] = useState<AppTab>(initialView.kind === "tab" ? initialView.tab : "sessions");
  const [viewSessionId, setViewSessionId] = useState<string | null>(
    initialView.kind === "session" ? initialView.sessionId : null,
  );
  const [openTask, setOpenTask] = useState<string | null>(
    initialView.kind === "tab" ? (initialView.task ?? null) : null,
  );
  // The project a real card/sub-task click already named for `openTask` -
  // never part of the URL (§6.5's literal `?task=<folder>&tab=...` shape),
  // so it's always `null` on first load: Kanban.tsx falls back to its own
  // cross-project folder lookup in that case, same as before this existed.
  const [openTaskProject, setOpenTaskProject] = useState<string | null>(null);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>(
    initialView.kind === "tab" ? (initialView.drawerTab ?? "details") : "details",
  );
  // The board's own visible project filter, part of the URL (`?project=`)
  // unlike `openTaskProject` above - kept across tab switches (unlike
  // `openTask`/`openTaskProject`, which reset) so returning to Kanban later
  // restores the same filter.
  const [boardProject, setBoardProject] = useState<string | undefined>(
    initialView.kind === "tab" ? initialView.boardProject : undefined,
  );

  function navigateToTab(tab: AppTab) {
    setActiveTabState(tab);
    setViewSessionId(null);
    setOpenTask(null);
    setOpenTaskProject(null);
    const path = pathForView({ kind: "tab", tab, boardProject });
    if (path !== window.location.pathname) window.history.pushState(null, "", path);
  }

  function navigateToSession(sessionId: string) {
    setViewSessionId(sessionId);
    setActiveTabState("sessions");
    const path = pathForView({ kind: "session", sessionId });
    if (path !== window.location.pathname) window.history.pushState(null, "", path);
  }

  // Task drawer URL state (PRD §6.5): `task: null` closes it. Always
  // pushes (not replaces) so the drawer's own open/close/tab-change history
  // is real browser-back-able, matching `navigateToTab`/`navigateToSession`'s
  // own convention.
  function navigateToTask(task: string | null, tab: DrawerTab = "details", project?: string) {
    setOpenTask(task);
    setOpenTaskProject(project ?? null);
    setDrawerTab(tab);
    setActiveTabState("kanban");
    const path = pathForView({ kind: "tab", tab: "kanban", task: task ?? undefined, drawerTab: tab, boardProject });
    const current = window.location.pathname + window.location.search;
    if (path !== current) window.history.pushState(null, "", path);
  }

  // A filter change isn't a back-button-worthy navigation event (same
  // judgment Overview's own `updateSearchParams` makes for its identical
  // `?project=` filter on a different path) - `replaceState`, not `pushState`.
  function onBoardProjectChange(project: string | undefined) {
    setBoardProject(project);
    const path = pathForView({
      kind: "tab",
      tab: "kanban",
      task: openTask ?? undefined,
      drawerTab,
      boardProject: project,
    });
    window.history.replaceState(null, "", path);
  }

  useEffect(() => {
    // Regression guard (App.test.tsx): every other page (Overview/
    // SessionsList) owns its own query-string state (sort/dir/page/range)
    // that this normalization must not silently drop - only Kanban's own
    // task/tab pair is derived from `view` itself, so only its path is
    // rebuilt from `pathForView` alone; everywhere else keeps the original
    // search string verbatim.
    const view = parseView(window.location.pathname, window.location.search);
    const isKanban = view.kind === "tab" && view.tab === "kanban";
    const path = isKanban ? pathForView(view) : pathForView(view) + window.location.search;
    window.history.replaceState(null, "", path);
  }, []);

  useEffect(() => {
    function onPopState() {
      const view = parseView(window.location.pathname, window.location.search);
      if (view.kind === "session") {
        setViewSessionId(view.sessionId);
        setActiveTabState("sessions");
        setOpenTask(null);
        setOpenTaskProject(null);
      } else {
        setViewSessionId(null);
        setActiveTabState(view.tab);
        setOpenTask(view.task ?? null);
        // Back/forward restores from the URL alone, which never carries
        // `project` (§6.5) - Kanban.tsx's own cross-project folder lookup
        // resolves it instead, same as a hard reload.
        setOpenTaskProject(null);
        setDrawerTab(view.drawerTab ?? "details");
        // parseView only ever populates `boardProject` on the /kanban path -
        // a popstate landing on Overview/Sessions never carries a `project`
        // param, so only touch `boardProject` when the landing view is
        // actually Kanban. Otherwise leave it as-is, mirroring how
        // `navigateToTab` preserves it by never calling `setBoardProject`.
        if (view.tab === "kanban") setBoardProject(view.boardProject);
      }
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (viewSessionId) {
    return (
      <Drilldown
        sessionId={viewSessionId}
        activeTab={activeTab}
        onTabChange={navigateToTab}
        onBack={() => navigateToTab("sessions")}
      />
    );
  }

  if (activeTab === "overview") {
    return <Overview activeTab={activeTab} onTabChange={navigateToTab} />;
  }

  if (activeTab === "kanban") {
    return (
      <Kanban
        activeTab={activeTab}
        onTabChange={navigateToTab}
        openTask={openTask}
        openTaskProject={openTaskProject}
        drawerTab={drawerTab}
        onOpenTask={navigateToTask}
        boardProject={boardProject}
        onBoardProjectChange={onBoardProjectChange}
      />
    );
  }

  return <SessionsList activeTab={activeTab} onTabChange={navigateToTab} onSelectSession={navigateToSession} />;
}
