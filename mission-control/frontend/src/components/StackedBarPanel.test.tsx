import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StackedBarPanel } from "./StackedBarPanel";

describe("StackedBarPanel", () => {
  it("sizes each segment by its share of the total value", () => {
    render(
      <StackedBarPanel
        data-testid="by-model"
        rows={[
          { key: "sonnet-5", value: 70, display: "$131.00" },
          { key: "opus-5.5", value: 30, display: "$48.60" },
        ]}
      />,
    );

    // Rendered as Recharts <rect> segments (pixel `width` attributes off the
    // 800px stubbed container, not a CSS percentage) - assert the 70/30
    // proportion rather than an exact pixel figure.
    const seg1Width = Number(screen.getByTestId("by-model-seg-sonnet-5").getAttribute("width"));
    const seg2Width = Number(screen.getByTestId("by-model-seg-opus-5.5").getAttribute("width"));
    expect(seg1Width).toBeGreaterThan(seg2Width);
    expect(seg1Width / (seg1Width + seg2Width)).toBeCloseTo(0.7, 1);
    expect(screen.getByTestId("by-model-legend-sonnet-5")).toHaveTextContent("sonnet-5");
    expect(screen.getByTestId("by-model-legend-sonnet-5")).toHaveTextContent("$131.00");
  });

  it("shows the empty text instead of a zero-width bar when there's no data", () => {
    render(<StackedBarPanel rows={[]} emptyText="No tool calls yet." />);
    expect(screen.getByText("No tool calls yet.")).toBeInTheDocument();
  });

  // `rows` is `[]` both while a rollup query is still in flight and once it
  // resolves to genuinely empty - `loading` disambiguates them so a fetch in
  // progress doesn't flash the empty-text message.
  it("shows a skeleton instead of the empty text while loading", () => {
    render(<StackedBarPanel data-testid="by-tools" rows={[]} loading emptyText="No tool calls yet." />);
    expect(screen.queryByText("No tool calls yet.")).not.toBeInTheDocument();
    expect(screen.getByTestId("by-tools-loading")).toBeInTheDocument();
  });

  // F6: ProjectCostPanel is this component's first click-to-filter
  // consumer - By models/tools/agents (O3) never pass onSelectRow, so their
  // legend rows stay non-interactive.
  it("F6: reports the clicked row's key via onSelectRow, and marks the selected row", () => {
    const onSelectRow = vi.fn();
    render(
      <StackedBarPanel
        data-testid="by-project"
        selectedKey="wardstone"
        onSelectRow={onSelectRow}
        rows={[
          { key: "cairn-2.0", value: 70, display: "$125.50" },
          { key: "wardstone", value: 30, display: "$45.00" },
        ]}
      />,
    );

    expect(screen.getByTestId("by-project-legend-wardstone")).toHaveClass("selected");
    fireEvent.click(screen.getByTestId("by-project-legend-cairn-2.0"));
    expect(onSelectRow).toHaveBeenCalledWith("cairn-2.0");
  });
});
