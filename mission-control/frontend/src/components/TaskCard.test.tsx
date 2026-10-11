import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TaskCard as TaskCardData } from "../api/types";
import { TaskCard } from "./TaskCard";

function task(overrides: Partial<TaskCardData> = {}): TaskCardData {
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

describe("TaskCard", () => {
  it("renders the folder's display name, goal, and kind, with no project tag on a single-project install", () => {
    render(<TaskCard task={task()} showProject={false} />);

    expect(screen.getByText("build-kanban-board")).toBeInTheDocument();
    expect(screen.getByText("Cross-project kanban board in mission-control.")).toBeInTheDocument();
    expect(screen.getByText("build")).toBeInTheDocument();
    expect(screen.queryByText("cairn-2.0")).not.toBeInTheDocument();
  });

  it("shows the project tag on a multi-project install", () => {
    render(<TaskCard task={task()} showProject />);
    expect(screen.getByText("cairn-2.0")).toBeInTheDocument();
  });

  it("shows the sub-task parent indicator using the parent's own display name", () => {
    render(
      <TaskCard
        task={task({ folder: "docs/tasks/2026-.../02-build-cleanup-fixtures", parent: "docs/tasks/2026-09-01-task-folder-cleanup" })}
        showProject={false}
      />,
    );
    expect(screen.getByTestId("kcard-parent")).toHaveTextContent("task-folder-cleanup");
  });

  it("renders an accurate N of M done progress bar for a parent with sub-tasks", () => {
    render(<TaskCard task={task({ sub_tasks: { done: 1, total: 3 } })} showProject={false} />);
    expect(screen.getByText("1 of 3 done")).toBeInTheDocument();
    const fill = document.querySelector(".hbar-fill") as HTMLElement;
    expect(fill.style.width).toBe("33%");
  });

  it("omits the progress bar entirely when there are no sub-tasks", () => {
    render(<TaskCard task={task({ sub_tasks: null })} showProject={false} />);
    expect(document.querySelector(".kcard-progress")).not.toBeInTheDocument();
  });

  it("shows the matched attention trigger phrase for a needs_attention card in any column", () => {
    render(
      <TaskCard task={task({ column: "building", needs_attention: true, key_info: "stalled since last week" })} showProject={false} />,
    );
    expect(screen.getByText("stalled")).toBeInTheDocument();
    expect(screen.queryByText("active")).not.toBeInTheDocument();
  });

  it("shows the active badge for an active card", () => {
    render(<TaskCard task={task({ column: "building", active: true })} showProject={false} />);
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(document.querySelector(".kcard-attn")).not.toBeInTheDocument();
  });

  it("shows both badges together when a card is active and needs attention", () => {
    render(<TaskCard task={task({ column: "building", active: true, needs_attention: true, key_info: "needs-human" })} showProject={false} />);
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("needs-human")).toBeInTheDocument();
  });

  it("shows neither badge when neither boolean is set", () => {
    render(<TaskCard task={task({ column: "done" })} showProject={false} />);
    expect(screen.queryByText("active")).not.toBeInTheDocument();
    expect(document.querySelector(".kcard-attn")).not.toBeInTheDocument();
  });

  it("shows the last-touched date in Overview's readable day format, not the terse MM-DD form", () => {
    render(<TaskCard task={task({ last_log_date: "2019-01-05" })} showProject={false} />);
    expect(screen.getByText("last touched Jan 5 2019, Sat")).toBeInTheDocument();
    expect(screen.queryByText(/last touched 01-05/)).not.toBeInTheDocument();
  });

  it("shows relative time instead of the date when the last log line carries a time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-29T10:00:00Z"));
    try {
      render(<TaskCard task={task({ last_log_date: "2026-09-28", last_log_time: "11:00" })} showProject={false} />);
      expect(screen.getByText("last touched 23h ago")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("passes its own already-known project alongside its folder on click, so the caller never has to re-derive it by folder alone", () => {
    const onClick = vi.fn();
    const cardTask = task({ project: "project-b", folder: "docs/tasks/0001-shared-folder-name" });
    render(<TaskCard task={cardTask} showProject onClick={onClick} />);

    fireEvent.click(screen.getByTestId(`task-card-${cardTask.folder}`));

    expect(onClick).toHaveBeenCalledWith("project-b", "docs/tasks/0001-shared-folder-name");
  });
});
