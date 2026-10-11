import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TaskCard } from "../api/types";
import { _resetAttentionModuleStateForTests } from "../lib/attention";
import { envelope, installFetchMock, serverError } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { Kanban } from "./Kanban";

const noop = () => {};

function task(overrides: Partial<TaskCard> = {}): TaskCard {
  return {
    project: "cairn-2.0",
    folder: "docs/tasks/2026-09-28-1345-build-kanban-board",
    parent: null,
    kind: "build",
    goal: "Cross-project kanban board in mission-control.",
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

function install(tasks: TaskCard[], projects = [{ label: "cairn-2.0", parent: null }]) {
  return installFetchMock({
    "/api/projects": () => envelope({ hostname: "test-host", projects }),
    "/api/tasks": () => envelope(tasks),
  });
}

// The drawer itself (TaskDrawer.tsx) has its own test file - these tests
// only cover Kanban's own wiring: a card click reports its folder up via
// `onOpenTask`, and the drawer mounts once `openTask`/its resolved project
// are both known.
function renderKanban(overrides: Partial<Parameters<typeof Kanban>[0]> = {}) {
  return renderWithClient(
    <Kanban
      activeTab="kanban"
      onTabChange={noop}
      openTask={null}
      openTaskProject={null}
      drawerTab="details"
      onOpenTask={noop}
      boardProject={undefined}
      onBoardProjectChange={noop}
      {...overrides}
    />,
  );
}

// Only the project-filter-change regression test below needs to rerender
// with new props against the *same* QueryClient (so its cache/query-key
// change is real, not a fresh mount) - `renderKanban`/`renderWithClient`
// don't expose the client for that, so this wraps `Kanban` the same way but
// keeps a `rerenderKanban` that reuses it.
function renderKanbanRerenderable(overrides: Partial<Parameters<typeof Kanban>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 }, mutations: { retry: false } } });
  const props: Parameters<typeof Kanban>[0] = {
    activeTab: "kanban",
    onTabChange: noop,
    openTask: null,
    openTaskProject: null,
    drawerTab: "details",
    onOpenTask: noop,
    boardProject: undefined,
    onBoardProjectChange: noop,
    ...overrides,
  };
  const result = render(
    <QueryClientProvider client={client}>
      <Kanban {...props} />
    </QueryClientProvider>,
  );
  return {
    ...result,
    rerenderKanban: (nextOverrides: Partial<Parameters<typeof Kanban>[0]>) =>
      result.rerender(
        <QueryClientProvider client={client}>
          <Kanban {...{ ...props, ...nextOverrides }} />
        </QueryClientProvider>,
      ),
  };
}

describe("Kanban", () => {
  // AppHeader (mounted by every page, including this one) reads/writes
  // module-level attention-signaling state that would otherwise leak
  // between tests in different files run in the same worker.
  beforeEach(() => {
    _resetAttentionModuleStateForTests();
  });

  it("renders the parent tasks column then the seven lifecycle stage columns in order", async () => {
    install([task()]);
    renderKanban();

    await waitFor(() => expect(screen.getByText("build-kanban-board")).toBeInTheDocument());
    const titles = screen.getAllByText(/./, { selector: ".kanban-column-title" });
    expect(titles.map((el) => el.textContent)).toEqual([
      "Parent tasks",
      "Scoping",
      "Awaiting approval",
      "Planned",
      "Building",
      "In review",
      "Blocked",
      "Done",
    ]);
  });

  it("shows attention and active as badges inside the card's own stage column, and no attention badge on an awaiting-approval card", async () => {
    install([
      task({ folder: "docs/tasks/2026-09-02-0900-attn-one", column: "building", needs_attention: true, key_info: "needs-human" }),
      task({ folder: "docs/tasks/2026-09-03-0900-live-one", column: "building", active: true }),
      task({
        folder: "docs/tasks/2026-09-06-0900-await-one",
        column: "awaiting_approval",
        key_info: "awaiting plan approval",
      }),
    ]);
    renderKanban();

    const attn = await screen.findByTestId("task-card-docs/tasks/2026-09-02-0900-attn-one");
    expect(attn.closest(".kanban-column-cards")?.previousElementSibling).toHaveTextContent("Building");
    expect(within(attn).getByText("needs-human")).toBeInTheDocument();
    const live = screen.getByTestId("task-card-docs/tasks/2026-09-03-0900-live-one");
    expect(within(live).getByText("active")).toBeInTheDocument();
    const await1 = screen.getByTestId("task-card-docs/tasks/2026-09-06-0900-await-one");
    expect(await1.closest(".kanban-column-cards")?.previousElementSibling).toHaveTextContent("Awaiting approval");
    expect(await1.querySelector(".kcard-attn")).toBeNull();
  });

  it("renders a parent_tasks card under the Parent tasks column", async () => {
    install([
      task({
        folder: "docs/tasks/2026-09-08-0900-parent-one",
        column: "parent_tasks",
        sub_tasks: { done: 1, total: 3 },
      }),
    ]);
    renderKanban();

    const parent = await screen.findByTestId("task-card-docs/tasks/2026-09-08-0900-parent-one");
    expect(parent.closest(".kanban-column-cards")?.previousElementSibling).toHaveTextContent("Parent tasks");
  });

  it("groups a real /api/tasks response into its columns", async () => {
    install([
      task({ folder: "docs/tasks/2026-09-01-0900-ready-one", column: "scoping" }),
      task({ folder: "docs/tasks/2026-09-02-0900-attn-one", column: "building", needs_attention: true, key_info: "needs-human" }),
      task({ folder: "docs/tasks/2026-09-03-0900-ongoing-one", column: "in_review" }),
      task({ folder: "docs/tasks/2026-09-04-0900-done-one", column: "done" }),
      task({ folder: "docs/tasks/2026-09-05-0900-done-two", column: "done" }),
      task({
        folder: "docs/tasks/2026-09-07-0900-stuck-one",
        column: "blocked",
        needs_attention: true,
        key_info: "blocked on X",
      }),
    ]);
    renderKanban();

    await waitFor(() => expect(screen.getByText("ready-one")).toBeInTheDocument());
    expect(screen.getByText("attn-one")).toBeInTheDocument();
    expect(screen.getByText("ongoing-one")).toBeInTheDocument();
    expect(screen.getByText("done-one")).toBeInTheDocument();
    expect(screen.getByText("done-two")).toBeInTheDocument();

    const columns = screen.getAllByText(/^\d+$/, { selector: ".kanban-column-count" });
    expect(columns.map((el) => el.textContent)).toEqual(["0", "1", "0", "0", "1", "1", "1", "2"]);
    const stuck = screen.getByTestId("task-card-docs/tasks/2026-09-07-0900-stuck-one");
    expect(stuck.closest(".kanban-column-cards")?.previousElementSibling).toHaveTextContent("Blocked");
    expect(stuck.querySelector(".kcard-attn")).not.toBeNull();
  });

  it("renders two sibling sub-task cards under the same parent as ordinary cards in different columns, and shows the parent's own N of M done bar", async () => {
    const parentFolder = "docs/tasks/2026-09-01-0900-parent";
    install([
      task({
        folder: parentFolder,
        column: "building",
        sub_tasks: { done: 1, total: 2 },
      }),
      task({
        folder: `${parentFolder}/01-build-first`,
        parent: parentFolder,
        column: "done",
      }),
      task({
        folder: `${parentFolder}/02-build-second`,
        parent: parentFolder,
        column: "building",
        needs_attention: true,
        key_info: "stalled",
      }),
    ]);
    renderKanban();

    await waitFor(() => expect(screen.getByText("1 of 2 done")).toBeInTheDocument());
    expect(screen.getByTestId(`task-card-${parentFolder}/01-build-first`)).toBeInTheDocument();
    expect(screen.getByTestId(`task-card-${parentFolder}/02-build-second`)).toBeInTheDocument();
    // §6.3: siblings are ordinary, unattached cards in different columns -
    // not nested under or adjacent to the parent, just linked by the
    // parent-reference indicator.
    expect(screen.getAllByTestId("kcard-parent")).toHaveLength(2);
  });

  it("Refresh now refetches projects, the filtered tasks list and the unfiltered tasks list, spinning until they settle", async () => {
    const calls: string[] = [];
    let hold: Promise<void> | null = null;
    let release: (() => void) | undefined;
    const fetchMock = installFetchMock({
      "/api/projects": () => {
        calls.push("projects");
        return envelope({ hostname: "test-host", projects: [{ label: "project-a", parent: null }, { label: "project-b", parent: null }] });
      },
      "/api/tasks": (params) => {
        calls.push(`tasks:${params.get("project") ?? ""}`);
        return envelope([task({ folder: "docs/tasks/2026-09-01-0900-ready-one", project: "project-a" })]);
      },
    });
    const inner = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input) => {
      if (hold && String(input).startsWith("/api/tasks")) await hold;
      return inner!(input);
    });
    renderKanban({ boardProject: "project-a" });

    await screen.findByTestId("task-card-docs/tasks/2026-09-01-0900-ready-one");
    await waitFor(() => expect(calls).toEqual(expect.arrayContaining(["projects", "tasks:project-a", "tasks:"])));
    const before = calls.length;
    hold = new Promise<void>((resolve) => {
      release = resolve;
    });

    const button = screen.getByRole("button", { name: "Refresh now" });
    expect(document.querySelector(".updated-at")).toBeNull();
    fireEvent.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveClass("spinning");
    release?.();
    await waitFor(() => expect(button).toBeEnabled());
    expect(button).not.toHaveClass("spinning");
    const fresh = calls.slice(before);
    expect(fresh).toEqual(expect.arrayContaining(["projects", "tasks:project-a", "tasks:"]));
    expect(document.querySelector(".updated-at")).toHaveTextContent(/^updated/);
  });

  it("Refresh now on an unfiltered board re-enables the button and shows the updated label", async () => {
    install([task()]);
    renderKanban();

    await screen.findByTestId("task-card-docs/tasks/2026-09-28-1345-build-kanban-board");
    fireEvent.click(screen.getByRole("button", { name: "Refresh now" }));

    await waitFor(() => expect(document.querySelector(".updated-at")).toHaveTextContent(/^updated/));
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeEnabled();
  });

  it("shows the empty state when the project has no task folders", async () => {
    install([]);
    renderKanban();

    await waitFor(() => expect(screen.getByTestId("kanban-empty")).toBeInTheDocument());
    expect(screen.getByText("No task folders yet")).toBeInTheDocument();
  });

  it("reports a clicked card's folder and its own already-known project up via onOpenTask (§6.5's wiring, not the drawer's own content)", async () => {
    const folder = "docs/tasks/2026-09-01-0900-ready-one";
    install([task({ folder, column: "planned", project: "cairn-2.0" })]);
    const onOpenTask = vi.fn();
    renderKanban({ onOpenTask });

    await waitFor(() => expect(screen.getByTestId(`task-card-${folder}`)).toBeInTheDocument());
    fireEvent.click(screen.getByTestId(`task-card-${folder}`));

    expect(onOpenTask).toHaveBeenCalledWith(folder, "details", "cairn-2.0");
  });

  it("opens the clicked project's own drawer content, not the first project sharing that folder name (a real click's project bypasses the by-folder-only fallback lookup)", async () => {
    const folder = "docs/tasks/0001-shared-folder-name";
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "project-a", parent: null },
            { label: "project-b", parent: null },
          ],
        }),
      "/api/tasks": () =>
        envelope([
          task({ project: "project-a", folder, goal: "Project A's own task" }),
          task({ project: "project-b", folder, goal: "Project B's own task" }),
        ]),
      "/api/tasks/detail": (params) =>
        envelope({
          project: params.get("project"),
          folder,
          parent: null,
          kind: "build",
          column: "planned",
          frontmatter: { goal: params.get("project") === "project-b" ? "Project B's own task" : "Project A's own task" },
          activity: [],
          draft_content: null,
          sub_tasks: null,
          docs: [],
        }),
    });
    // Simulates the render right after a direct click on project-b's card:
    // `openTaskProject` is already known, so Kanban must not fall back to
    // `allTasks.data.find()`'s first-match-wins-by-folder lookup, which
    // would resolve project-a instead (it's first in `/api/tasks`).
    renderKanban({ openTask: folder, openTaskProject: "project-b" });

    // Scoped to the drawer itself - both projects' own cards behind it
    // legitimately render "Project A's/B's own task" as their goal text, so
    // only the drawer's own content is a meaningful assertion here.
    const drawer = within(await screen.findByTestId("task-drawer"));
    await waitFor(() => expect(drawer.getByText("Project B's own task")).toBeInTheDocument());
    expect(drawer.queryByText("Project A's own task")).not.toBeInTheDocument();
  });

  it("mounts the drawer once openTask's project resolves from the (unfiltered) task list", async () => {
    const folder = "docs/tasks/2026-09-01-0900-ready-one";
    install([task({ folder, column: "planned" })]);
    installFetchMock({
      "/api/projects": () => envelope({ hostname: "test-host", projects: [{ label: "cairn-2.0", parent: null }] }),
      "/api/tasks": () => envelope([task({ folder, column: "planned" })]),
      "/api/tasks/detail": () =>
        envelope({
          project: "cairn-2.0",
          folder,
          parent: null,
          kind: "build",
          column: "planned",
          frontmatter: { goal: "g" },
          activity: [],
          draft_content: null,
          sub_tasks: null,
          docs: [],
        }),
    });
    renderKanban({ openTask: folder, drawerTab: "details" });

    await waitFor(() => expect(screen.getByTestId("task-drawer")).toBeInTheDocument());
  });

  it("reports a picked project up via onBoardProjectChange rather than filtering from local state (the filter now lives in App.tsx's URL)", async () => {
    install(
      [task({ folder: "docs/tasks/2026-09-01-0900-ready-one", project: "project-a" })],
      [
        { label: "project-a", parent: null },
        { label: "project-b", parent: null },
      ],
    );
    const onBoardProjectChange = vi.fn();
    renderKanban({ onBoardProjectChange });

    await waitFor(() => expect(screen.getByTestId("install-scope-dropdown")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("install-scope-dropdown"));
    fireEvent.click(screen.getByTestId("install-scope-option-project-b"));

    expect(onBoardProjectChange).toHaveBeenCalledWith("project-b");
  });

  it("renders the chip and clears via onBoardProjectChange when boardProject is already set (reload-restored filter, not local state)", async () => {
    install(
      [task({ folder: "docs/tasks/2026-09-01-0900-ready-one", project: "project-a" })],
      [
        { label: "project-a", parent: null },
        { label: "project-b", parent: null },
      ],
    );
    const onBoardProjectChange = vi.fn();
    renderKanban({ boardProject: "project-a", onBoardProjectChange });

    const chip = await screen.findByTestId("install-scope-chip");
    expect(chip).toHaveTextContent("project-a");
    fireEvent.click(within(chip).getByTitle("Clear filter"));

    expect(onBoardProjectChange).toHaveBeenCalledWith(undefined);
  });

  it("pages a column's cards behind a manual See more control", async () => {
    const tasks = Array.from({ length: 25 }, (_, i) =>
      task({ folder: `docs/tasks/2026-09-01-0900-ready-${i}`, column: "planned" }),
    );
    install(tasks);
    renderKanban();

    await waitFor(() => expect(screen.getByTestId(`task-card-${tasks[0].folder}`)).toBeInTheDocument());
    expect(screen.queryByTestId(`task-card-${tasks[20].folder}`)).not.toBeInTheDocument();
    const seeMore = screen.getByTestId("kanban-see-more-planned");
    expect(seeMore).toHaveTextContent("See more");

    fireEvent.click(seeMore);

    for (const t of tasks) {
      expect(screen.getByTestId(`task-card-${t.folder}`)).toBeInTheDocument();
    }
    expect(screen.queryByTestId("kanban-see-more-planned")).not.toBeInTheDocument();
    expect(screen.queryByRole("separator")).toBeNull();
  });

  it("resets a column's paging back to page 1 when the board's project filter changes, even after paging past the end (shown state is owned by Kanban itself, one level above the keyed kanban-columns subtree)", async () => {
    const readyTasksFor = (project: string) =>
      Array.from({ length: 25 }, (_, i) =>
        task({ folder: `docs/tasks/2026-09-01-0900-${project}-ready-${i}`, column: "planned", project }),
      );
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "project-a", parent: null },
            { label: "project-b", parent: null },
          ],
        }),
      "/api/tasks": (params) => envelope(readyTasksFor(params.get("project") ?? "project-a")),
    });
    const { rerenderKanban } = renderKanbanRerenderable({ boardProject: "project-a" });

    // Page past the end of project-a's ready column (25 cards, PAGE_SIZE 20
    // - one "See more" click reveals all 25 and replaces the button with the
    // end marker).
    await waitFor(() => expect(screen.getByTestId("kanban-see-more-planned")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("kanban-see-more-planned"));
    await waitFor(() => expect(screen.getByTestId("task-card-docs/tasks/2026-09-01-0900-project-a-ready-24")).toBeInTheDocument());

    rerenderKanban({ boardProject: "project-b" });

    // project-b also has 25 ready cards - if `shown.ready` had carried over
    // (the bug), the end marker would still be showing all 25. A real reset
    // brings back the first page only, with "See more" reappearing.
    await waitFor(() => expect(screen.getByTestId("kanban-see-more-planned")).toBeInTheDocument());
    expect(screen.getByTestId("task-card-docs/tasks/2026-09-01-0900-project-b-ready-0")).toBeInTheDocument();
    expect(screen.queryByTestId("task-card-docs/tasks/2026-09-01-0900-project-b-ready-24")).not.toBeInTheDocument();
  });

  it("renders an empty column with no end marker, without triggering the board's own all-empty state", async () => {
    install([task({ folder: "docs/tasks/2026-09-01-0900-ready-one", column: "planned" })]);
    renderKanban();

    await waitFor(() => expect(screen.getByTestId("task-card-docs/tasks/2026-09-01-0900-ready-one")).toBeInTheDocument());
    const doneCount = screen.getAllByText(/^\d+$/, { selector: ".kanban-column-count" }).at(-1);
    expect(doneCount).toHaveTextContent("0");
    expect(screen.queryByTestId("kanban-empty")).not.toBeInTheDocument();
    expect(screen.queryByTestId("kanban-see-more-done")).not.toBeInTheDocument();
    expect(screen.queryByRole("separator")).toBeNull();
  });

  it("shows skeleton cards in every column while the first tasks fetch is pending, then swaps them for the real board", async () => {
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const fetchMock = install([task({ column: "planned" })]);
    const inner = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input) => {
      if (String(input).startsWith("/api/tasks")) await gate;
      return inner!(input);
    });
    renderKanban();

    await waitFor(() => expect(screen.getAllByTestId("kanban-skel")).toHaveLength(24));
    expect(screen.queryByTestId("kanban-empty")).not.toBeInTheDocument();

    release?.();
    await waitFor(() => expect(screen.queryByTestId("kanban-skel")).not.toBeInTheDocument());
    expect(screen.getByTestId("task-card-docs/tasks/2026-09-28-1345-build-kanban-board")).toBeInTheDocument();
  });

  it("shows an error state with retry when /api/tasks fails", async () => {
    const fetchMock = installFetchMock({
      "/api/projects": () => envelope({ hostname: "test-host", projects: [{ label: "cairn-2.0", parent: null }] }),
      "/api/tasks": () => serverError(),
    });
    renderKanban();

    await waitFor(() => expect(screen.getByTestId("kanban-error-text")).toBeInTheDocument());
    const callsBeforeRetry = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByTestId("kanban-error-retry"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry));
  });
});
