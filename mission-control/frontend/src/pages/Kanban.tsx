import { useEffect, useState } from "react";
import { useProjects, useTasks } from "../api/hooks";
import type { TaskCard as TaskCardData, TaskColumn } from "../api/types";
import { AppHeader, type AppTab } from "../components/AppHeader";
import { InstallScopeRow } from "../components/InstallScopeRow";
import { KanbanIcon } from "../components/icons";
import { PanelError } from "../components/PanelError";
import { StateCard } from "../components/StateCard";
import { TaskCard } from "../components/TaskCard";
import { TaskDrawer } from "../components/TaskDrawer";
import { formatRelativeToNow } from "../lib/format";

type DrawerTab = "details" | "docs";

interface KanbanProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  // Drawer URL state lives in App.tsx (PRD §6.5) - `openTask` is a folder
  // path or `null` (closed); the URL itself never carries `project`, per
  // §6.5's literal `?task=<folder>&tab=...` shape. `openTaskProject` is
  // App.tsx's own session-only memory of the project a real click already
  // named (`null` on first load/URL-restore/back-forward, where there is
  // genuinely no other way to know it yet) - this page falls back to the
  // cross-project task list's own folder lookup only in that case.
  openTask: string | null;
  openTaskProject: string | null;
  drawerTab: DrawerTab;
  onOpenTask: (task: string | null, tab?: DrawerTab, project?: string) => void;
  // The board's own visible project filter - unlike `openTaskProject` above,
  // this one lives in the URL (App.tsx's `?project=`) so a reload restores
  // it, matching every other filter in this app.
  boardProject: string | undefined;
  onBoardProjectChange: (project: string | undefined) => void;
}

const COLUMNS: { key: TaskColumn; title: string }[] = [
  { key: "parent_tasks", title: "Parent tasks" },
  { key: "scoping", title: "Scoping" },
  { key: "awaiting_approval", title: "Awaiting approval" },
  { key: "planned", title: "Planned" },
  { key: "building", title: "Building" },
  { key: "in_review", title: "In review" },
  { key: "blocked", title: "Blocked" },
  { key: "done", title: "Done" },
];

// Cards page behind a manual "See more" click (§ REQUIREMENTS.md Goals) - a
// fixed, implementation-chosen page size, not derived from the API.
const PAGE_SIZE = 20;

const initialShown = () => Object.fromEntries(COLUMNS.map((c) => [c.key, PAGE_SIZE])) as Record<TaskColumn, number>;

// pages/Kanban.tsx per `board-single-project.html`/`board-multi-project.
// html`/`board-empty.html`/`board-error.html` (PRD §6.1-§6.4) - fetches the
// flat `/api/tasks` list and groups it into 8 columns (parent tasks plus 7
// stages) client-side, same division of labor as every other list-shaped
// page in this app. Reuses
// AppHeader/InstallScopeRow verbatim (§9's install-type-reuse note - no new
// UI for single- vs. multi-project); the pill/title/favicon/chime (§6.9)
// already live inside AppHeader itself, not duplicated here.
export function Kanban({
  activeTab,
  onTabChange,
  openTask,
  openTaskProject,
  drawerTab,
  onOpenTask,
  boardProject,
  onBoardProjectChange,
}: KanbanProps) {
  const projects = useProjects();
  const hostTag = projects.data?.hostname ?? "localhost";
  const multiProject = (projects.data?.projects.length ?? 0) > 1;
  const tasks = useTasks(boardProject);
  // Unfiltered, so a drawer opened via a shared/reloaded URL can resolve its
  // folder's `project` even when the board's own dropdown has narrowed to a
  // different project - shares its cache/query with AppHeader's own
  // identical unfiltered call (`useTasks()`), so this is never an extra poll.
  const allTasks = useTasks();
  const drawerProject = openTask
    ? (openTaskProject ?? allTasks.data?.find((t) => t.folder === openTask)?.project ?? null)
    : null;

  // How many cards each column currently shows. `shown` is owned by this
  // component - one level above the `kanban-columns` div's own `key` below
  // - so changing that div's key on a project-filter change remounts the
  // column markup but does not reset this state; the effect below resets it
  // explicitly instead whenever `boardProject` changes.
  const [shown, setShown] = useState<Record<TaskColumn, number>>(initialShown);

  useEffect(() => {
    setShown(initialShown());
  }, [boardProject]);

  // Click-driven only (never `isFetching`), so the 5s poll never spins the
  // button. Refetches every query the board and its header show.
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await Promise.allSettled([projects.refetch(), tasks.refetch(), allTasks.refetch()]);
    } finally {
      setRefreshing(false);
      setLastUpdated(new Date());
    }
  }

  const grouped = Object.fromEntries(COLUMNS.map((c) => [c.key, [] as TaskCardData[]])) as Record<
    TaskColumn,
    TaskCardData[]
  >;
  for (const t of tasks.data ?? []) grouped[t.column]?.push(t);

  return (
    <div className="shell shell-board">
      <AppHeader
        activeTab={activeTab}
        onTabChange={onTabChange}
        connected={!projects.isError}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        updatedLabel={lastUpdated ? `updated ${formatRelativeToNow(lastUpdated.toISOString())}` : null}
      />

      <InstallScopeRow
        projects={projects.data?.projects ?? []}
        hostTag={hostTag}
        selectedProject={boardProject}
        onSelectProject={onBoardProjectChange}
      />

      {tasks.isError ? (
        <div
          className="panel err"
          style={{ flexGrow: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <PanelError
              message="Couldn't load task folders — GET /api/tasks failed"
              onRetry={() => tasks.refetch()}
              testId="kanban-error"
            />
          </div>
        </div>
      ) : tasks.isSuccess && tasks.data.length === 0 ? (
        <StateCard
          data-testid="kanban-empty"
          icon={<KanbanIcon />}
          title="No task folders yet"
          body={
            <>
              This project has no <code>docs/tasks/</code> folders — or only <code>_template/</code> — for cairn to
              show.
            </>
          }
        />
      ) : (
        <div className="kanban-columns" key={boardProject ?? "__all__"} aria-busy={tasks.isPending}>
          {COLUMNS.map((col) => (
            <div key={col.key} className="kanban-column">
              <div className="kanban-column-head">
                <span className="kanban-column-title">{col.title}</span>
                {!tasks.isPending && <span className="kanban-column-count">{grouped[col.key].length}</span>}
              </div>
              <div className="kanban-column-cards">
                {tasks.isPending &&
                  [0, 1, 2].map((i) => (
                    <div key={i} className="kcard-skel skel" aria-hidden="true" data-testid="kanban-skel" />
                  ))}
                {grouped[col.key].slice(0, shown[col.key]).map((t) => (
                  <TaskCard
                    key={`${t.project}::${t.folder}`}
                    task={t}
                    showProject={multiProject}
                    onClick={(project, folder) => onOpenTask(folder, "details", project)}
                  />
                ))}
                {!tasks.isPending && grouped[col.key].length > shown[col.key] && (
                  <button
                    className="btn-block"
                    onClick={() => setShown((prev) => ({ ...prev, [col.key]: prev[col.key] + PAGE_SIZE }))}
                    data-testid={`kanban-see-more-${col.key}`}
                  >
                    See more
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {openTask && drawerProject && (
        <TaskDrawer
          key={`${drawerProject}::${openTask}`}
          project={drawerProject}
          folder={openTask}
          tab={drawerTab}
          onClose={() => onOpenTask(null)}
          // Carries the already-resolved `drawerProject` along so a tab
          // switch doesn't drop back to the by-folder-only fallback lookup
          // on the next render.
          onTabChange={(tab) => onOpenTask(openTask, tab, drawerProject)}
          onOpenTask={(project, folder) => onOpenTask(folder, "details", project)}
        />
      )}
    </div>
  );
}
