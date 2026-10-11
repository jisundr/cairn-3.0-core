import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ProjectSummary, SessionSummary } from "../api/types";
import { ProjectCostPanel } from "./ProjectCostPanel";

function session(overrides: Partial<SessionSummary>): SessionSummary {
  return {
    session_id: "s1",
    project: "cairn-2.0",
    started: "2026-09-25T11:58:00Z",
    ended: "2026-09-25T12:39:00Z",
    agents: ["builder"],
    calls: 1,
    tokens: 100,
    cost: 5,
    usage_limit_hit: false,
    ...overrides,
  };
}

describe("ProjectCostPanel", () => {
  it("sums each project's cost and toggles the filter on row click", () => {
    const onSelectProject = vi.fn();
    const sessions = [session({ project: "cairn-2.0", cost: 5 }), session({ project: "cairn-2.0", cost: 7 }), session({ project: "wardstone", cost: 2 })];
    render(<ProjectCostPanel sessions={sessions} projects={[]} selectedProject={undefined} onSelectProject={onSelectProject} />);

    expect(screen.getByTestId("project-row-cairn-2.0")).toHaveTextContent("$12.00");
    expect(screen.getByTestId("project-row-wardstone")).toHaveTextContent("$2.00");

    fireEvent.click(screen.getByTestId("project-row-cairn-2.0"));
    expect(onSelectProject).toHaveBeenCalledWith("cairn-2.0");
  });

  it("clears the filter when the already-selected project's row is clicked again", () => {
    const onSelectProject = vi.fn();
    render(
      <ProjectCostPanel
        sessions={[session({ project: "cairn-2.0" })]}
        projects={[]}
        selectedProject="cairn-2.0"
        onSelectProject={onSelectProject}
      />,
    );

    fireEvent.click(screen.getByTestId("project-row-cairn-2.0"));
    expect(onSelectProject).toHaveBeenCalledWith(undefined);
  });

  it("marks a project unknown, with an info-mark, when any of its sessions has an unresolved cost", () => {
    render(
      <ProjectCostPanel
        sessions={[session({ project: "cairn-2.0", cost: null })]}
        projects={[]}
        selectedProject={undefined}
        onSelectProject={() => {}}
      />,
    );

    expect(screen.getByTestId("project-row-cairn-2.0")).toHaveTextContent("unknown");
    expect(screen.getAllByTitle("Model not yet priced").length).toBeGreaterThan(0);
  });

  it("goal 8: rolls a child project's sessions up into its parent's row", () => {
    const projects: ProjectSummary[] = [
      { label: "ai-worth-carrying", parent: null },
      { label: "engine", parent: "ai-worth-carrying" },
      { label: "site", parent: "ai-worth-carrying" },
    ];
    const sessions = [session({ project: "engine", cost: 3 }), session({ project: "site", cost: 4 })];
    const onSelectProject = vi.fn();
    render(<ProjectCostPanel sessions={sessions} projects={projects} selectedProject={undefined} onSelectProject={onSelectProject} />);

    expect(screen.getByTestId("project-row-ai-worth-carrying")).toHaveTextContent("$7.00");
    expect(screen.queryByTestId("project-row-engine")).not.toBeInTheDocument();
    expect(screen.queryByTestId("project-row-site")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("project-row-ai-worth-carrying"));
    expect(onSelectProject).toHaveBeenCalledWith("ai-worth-carrying");
  });
});
