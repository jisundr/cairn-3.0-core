import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ProjectSummary } from "../api/types";
import { InstallScopeRow } from "./InstallScopeRow";

describe("InstallScopeRow", () => {
  it("shows a read-only project chip on a single-project install", () => {
    const projects: ProjectSummary[] = [{ label: "cairn-2.0", parent: null }];
    render(<InstallScopeRow projects={projects} hostTag="host.local" selectedProject={undefined} onSelectProject={vi.fn()} />);

    expect(screen.getByTestId("install-scope-readonly")).toHaveTextContent("cairn-2.0");
    expect(screen.getByTestId("install-scope-host")).toHaveTextContent("host.local");
    expect(screen.queryByTestId("install-scope-dropdown")).not.toBeInTheDocument();
  });

  it("shows an All-projects dropdown on a multi-project install, and selecting an option filters", () => {
    const projects: ProjectSummary[] = [
      { label: "cairn-2.0", parent: null },
      { label: "wardstone", parent: null },
    ];
    const onSelectProject = vi.fn();
    render(<InstallScopeRow projects={projects} hostTag="host.local" selectedProject={undefined} onSelectProject={onSelectProject} />);

    expect(screen.getByTestId("install-scope-dropdown")).toHaveTextContent("All projects");
    fireEvent.click(screen.getByTestId("install-scope-dropdown"));
    fireEvent.click(screen.getByTestId("install-scope-option-wardstone"));

    expect(onSelectProject).toHaveBeenCalledWith("wardstone");
  });

  it("shows a clearable 'Project: X' chip once a project is selected on a multi-project install", () => {
    const projects: ProjectSummary[] = [
      { label: "cairn-2.0", parent: null },
      { label: "wardstone", parent: null },
    ];
    const onSelectProject = vi.fn();
    render(<InstallScopeRow projects={projects} hostTag="host.local" selectedProject="wardstone" onSelectProject={onSelectProject} />);

    const chip = screen.getByTestId("install-scope-chip");
    expect(chip).toHaveTextContent("Project: wardstone");

    fireEvent.click(chip.querySelector(".clear")!);
    expect(onSelectProject).toHaveBeenCalledWith(undefined);
  });

  it("shows nothing for the selected day by default, and a clearable date chip once one is selected", () => {
    const projects: ProjectSummary[] = [{ label: "cairn-2.0", parent: null }];
    const onClearDate = vi.fn();
    const { rerender } = render(
      <InstallScopeRow projects={projects} hostTag="host.local" selectedProject={undefined} onSelectProject={vi.fn()} />,
    );
    expect(screen.queryByTestId("install-scope-date-chip")).not.toBeInTheDocument();

    rerender(
      <InstallScopeRow
        projects={projects}
        hostTag="host.local"
        selectedProject={undefined}
        onSelectProject={vi.fn()}
        selectedDate="2026-09-25"
        onClearDate={onClearDate}
      />,
    );

    const chip = screen.getByTestId("install-scope-date-chip");
    expect(chip).toHaveTextContent("Date: Sep 25, Fri");
    fireEvent.click(chip.querySelector(".clear")!);
    expect(onClearDate).toHaveBeenCalled();
  });
});
