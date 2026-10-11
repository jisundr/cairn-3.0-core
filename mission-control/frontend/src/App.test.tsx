import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";
import type { SessionSummary, TaskCard } from "./api/types";
import { envelope, installFetchMock } from "./test/mockApi";
import { renderWithClient } from "./test/renderWithClient";

const SESSION: SessionSummary = {
  session_id: "a8de42aabbccddeeffgg1234c884",
  project: "cairn-2.0",
  started: "2026-09-25T11:58:00Z",
  ended: "2026-09-25T12:39:00Z",
  agents: ["builder"],
  calls: 12,
  tokens: 184204,
  cost: 12.4,
  usage_limit_hit: false,
};

function installSessionsHandlers() {
  return installFetchMock({
    "/api/projects": () => envelope({ hostname: "test-host", projects: [{ label: "cairn-2.0", parent: null }] }),
    "/api/rollup/session": () => envelope([SESSION]),
  });
}

function task(overrides: Partial<TaskCard> = {}): TaskCard {
  return {
    project: "project-a",
    folder: "docs/tasks/2026-09-01-0900-ready-one",
    parent: null,
    kind: "build",
    goal: "A task.",
    key_info: "in progress",
    last_log_date: "2026-09-28",
    last_log_time: "",
    column: "planned",
    active: false,
    needs_attention: false,
    done: false,
    sub_tasks: null,
    ...overrides,
  };
}

function installKanbanHandlers() {
  return installFetchMock({
    "/api/projects": () =>
      envelope({
        hostname: "test-host",
        projects: [
          { label: "project-a", parent: null },
          { label: "project-b", parent: null },
        ],
      }),
    "/api/tasks": (params) => {
      const project = params.get("project");
      const tasks = [task({ project: "project-a" }), task({ project: "project-b", folder: "docs/tasks/2026-09-02-0900-other" })];
      return envelope(project ? tasks.filter((t) => t.project === project) : tasks);
    },
  });
}

describe("App", () => {
  // A path/search set by an earlier test in this file would otherwise leak
  // into the next one's initial read.
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  // Regression: the mount effect that normalizes the URL (pathForView) used
  // to rebuild it from the pathname alone, silently dropping any query
  // string the page just loaded with - stripping the URL-state work done
  // in Overview/SessionsList right after it restored state from that same
  // query string.
  it("preserves the query string already in the URL when it mounts", async () => {
    window.history.pushState(null, "", "/sessions?sort=tokens&dir=desc&page=1");
    installSessionsHandlers();
    renderWithClient(<App />);

    await waitFor(() => expect(screen.getByTestId("sessions-table")).toBeInTheDocument());
    expect(window.location.pathname).toBe("/sessions");
    // SessionsList's own mount effect fills in its other params (e.g.
    // `range`) alongside these - this only asserts the ones already in the
    // URL before mount survive the App-level normalization effect.
    const params = new URLSearchParams(window.location.search);
    expect(params.get("sort")).toBe("tokens");
    expect(params.get("dir")).toBe("desc");
    expect(params.get("page")).toBe("1");
  });

  it("restores the Kanban project filter from ?project= on a reload, unlike its previous plain-state behavior", async () => {
    window.history.pushState(null, "", "/kanban?project=project-b");
    installKanbanHandlers();
    renderWithClient(<App />);

    const chip = await screen.findByTestId("install-scope-chip");
    expect(chip).toHaveTextContent("project-b");
    // Only project-b's own task should have loaded - proof the filter drove
    // `useTasks`'s own query, not just the chip's label.
    expect(screen.getByTestId("task-card-docs/tasks/2026-09-02-0900-other")).toBeInTheDocument();
    expect(screen.queryByTestId("task-card-docs/tasks/2026-09-01-0900-ready-one")).not.toBeInTheDocument();
  });

  it("updates the URL's project param on a filter change via replaceState, not a new history entry", async () => {
    window.history.pushState(null, "", "/kanban");
    installKanbanHandlers();
    renderWithClient(<App />);

    await waitFor(() => expect(screen.getByTestId("install-scope-dropdown")).toBeInTheDocument());
    const lengthBefore = window.history.length;

    fireEvent.click(screen.getByTestId("install-scope-dropdown"));
    fireEvent.click(screen.getByTestId("install-scope-option-project-b"));

    await waitFor(() => expect(new URLSearchParams(window.location.search).get("project")).toBe("project-b"));
    expect(window.history.length).toBe(lengthBefore);
  });

  it("restores the project filter from the URL on popstate (back/forward), same as task/tab", async () => {
    window.history.pushState(null, "", "/kanban");
    installKanbanHandlers();
    renderWithClient(<App />);

    await waitFor(() => expect(screen.getByTestId("install-scope-dropdown")).toBeInTheDocument());

    // Simulates a real back/forward: the URL already reflects the restored
    // entry by the time `popstate` fires, so the handler reads it straight
    // from `window.location` - same as `task`/`drawerTab` already do here.
    window.history.pushState(null, "", "/kanban?project=project-b");
    fireEvent.popState(window);

    await waitFor(() => expect(screen.getByTestId("install-scope-chip")).toHaveTextContent("project-b"));
  });

  // Regression (review finding on 4037070): `onPopState`'s shared non-
  // session branch used to call `setBoardProject(view.boardProject)`
  // unconditionally - but `parseView` only ever populates `boardProject` on
  // the /kanban path, so a popstate landing on Sessions or Overview (never
  // carrying `?project=`) silently cleared it, even though the user never
  // touched Kanban's filter in that navigation.
  it("keeps the Kanban project filter across a popstate landing on a non-Kanban tab", async () => {
    window.history.pushState(null, "", "/kanban?project=project-b");
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "project-a", parent: null },
            { label: "project-b", parent: null },
          ],
        }),
      "/api/tasks": (params) => {
        const project = params.get("project");
        const tasks = [
          task({ project: "project-a" }),
          task({ project: "project-b", folder: "docs/tasks/2026-09-02-0900-other" }),
        ];
        return envelope(project ? tasks.filter((t) => t.project === project) : tasks);
      },
      "/api/rollup/session": () => envelope([SESSION]),
    });
    renderWithClient(<App />);

    // Confirm the filter is actually applied before navigating away.
    await waitFor(() => expect(screen.getByTestId("install-scope-chip")).toHaveTextContent("project-b"));

    // Simulate the user's own navigation landing back on Sessions via
    // Back - `/sessions` never had a `project` param.
    window.history.pushState(null, "", "/sessions");
    fireEvent.popState(window);
    await waitFor(() => expect(screen.getByTestId("sessions-table")).toBeInTheDocument());

    // Returning to Kanban (a normal tab click, not another popstate) should
    // still carry the filter set before the trip to Sessions - proof
    // `boardProject` was never clobbered by the intervening popstate.
    fireEvent.click(screen.getByRole("link", { name: "Kanban" }));

    await waitFor(() => expect(screen.getByTestId("install-scope-chip")).toHaveTextContent("project-b"));
    expect(screen.getByTestId("task-card-docs/tasks/2026-09-02-0900-other")).toBeInTheDocument();
    expect(screen.queryByTestId("task-card-docs/tasks/2026-09-01-0900-ready-one")).not.toBeInTheDocument();
  });
});
