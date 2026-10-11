import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TimeseriesPoint } from "../api/types";
import { ContributionCalendar } from "./ContributionCalendar";

function point(bucket: string, tokens: number): TimeseriesPoint {
  return { bucket, calls: 1, tokens, cost: 0.1, by_model: [] };
}

describe("ContributionCalendar", () => {
  it("zero-fills the leading days of a range that doesn't start on a Monday", () => {
    // 2026-09-09 is a Wednesday - Mon/Tue of that week should render as
    // non-clickable zero-fill cells, not real (missing) dates.
    const points = [point("2026-09-09", 100), point("2026-09-10", 200)];
    const { container } = render(<ContributionCalendar points={points} selectedDate={null} onSelectDate={vi.fn()} />);

    const firstWeek = container.querySelector(".cal-week");
    const cells = firstWeek?.querySelectorAll(".cal-cell") ?? [];
    expect(cells[0]).toHaveClass("zerofill");
    expect(cells[1]).toHaveClass("zerofill");
    expect(cells[2]).not.toHaveClass("zerofill");
  });

  it("reports a clicked cell's date", () => {
    const points = [point("2026-09-09", 100), point("2026-09-10", 200)];
    const onSelectDate = vi.fn();
    render(<ContributionCalendar points={points} selectedDate={null} onSelectDate={onSelectDate} />);

    fireEvent.click(screen.getByTestId("cal-cell-2026-09-09"));
    expect(onSelectDate).toHaveBeenCalledWith("2026-09-09");
  });

  it("toggles off the already-selected cell on a repeat click", () => {
    const points = [point("2026-09-09", 100)];
    const onSelectDate = vi.fn();
    render(<ContributionCalendar points={points} selectedDate="2026-09-09" onSelectDate={onSelectDate} />);

    const cell = screen.getByTestId("cal-cell-2026-09-09");
    expect(cell).toHaveClass("selected");
    fireEvent.click(cell);
    expect(onSelectDate).toHaveBeenCalledWith(null);
  });
});
