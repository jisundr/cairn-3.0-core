import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HbarList, type HbarRow } from "./HbarList";

const ROWS: HbarRow[] = [
  { label: "Edit", value: 12, display: "12" },
  { label: "Bash", value: 8, display: "8" },
  { label: "Read", value: 5, display: "5" },
  { label: "Write", value: 2, display: "2" },
];

describe("HbarList", () => {
  it("shows only maxRows rows, then every row once 'Show all' is clicked", () => {
    render(<HbarList rows={ROWS} maxRows={2} data-testid="tool-rollup" />);

    expect(screen.getByTestId("tool-rollup")).toHaveTextContent("Edit");
    expect(screen.getByTestId("tool-rollup")).not.toHaveTextContent("Write");

    fireEvent.click(screen.getByTestId("tool-rollup-show-all"));

    expect(screen.getByTestId("tool-rollup")).toHaveTextContent("Write");
  });

  it("tags each row with rowTestId, textContent included, and shows an info-mark for an unknown-cost row", () => {
    const rows: HbarRow[] = [{ label: "sonnet-5", value: 100, display: "unknown", unknown: true }];
    render(<HbarList rows={rows} rowTestId={(r) => `model-row-${r.label}`} />);

    expect(screen.getByTestId("model-row-sonnet-5")).toHaveTextContent("unknown");
    expect(screen.getByTitle("Model not yet priced")).toBeInTheDocument();
  });

  it("renders emptyText instead of a chart when there are no rows", () => {
    render(<HbarList rows={[]} emptyText="No tool calls yet." />);
    expect(screen.getByText("No tool calls yet.")).toBeInTheDocument();
  });
});
