import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Timeseries } from "../api/types";
import { installFetchMock } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { buildChartData, buildSeries, TokensPerDayChart, tooltipDateLabel, tooltipRows } from "./TokensPerDayChart";

const TIMESERIES: Timeseries = {
  range: "7d",
  bucket: "day",
  since: "",
  until: "",
  points: [
    {
      bucket: "2026-09-24",
      calls: 3,
      tokens: 1000,
      cost: 1.0,
      by_model: [{ key: "claude-sonnet-5", calls: 3, tokens: 1000, cost: 1.0 }],
    },
    {
      bucket: "2026-09-25",
      calls: 5,
      tokens: 184204,
      cost: 12.4,
      by_model: [
        { key: "claude-sonnet-5", calls: 4, tokens: 150000, cost: 10.4 },
        { key: "claude-haiku-4.5", calls: 1, tokens: 34204, cost: 2.0 },
      ],
    },
  ],
  total_tokens: 185204,
  total_cost: 13.4,
};

describe("TokensPerDayChart", () => {
  it("renders a bar for every timeseries point, x-axis labels hidden", () => {
    installFetchMock({});
    const { container } = renderWithClient(<TokensPerDayChart timeseries={TIMESERIES} />);

    expect(screen.getByTestId("chart-bars")).toBeInTheDocument();
    expect(screen.getByTestId("chart-bar-2026-09-24")).toBeInTheDocument();
    expect(screen.getByTestId("chart-bar-2026-09-25")).toBeInTheDocument();
    // Observation on the live app: the day-number x-axis ticks read as
    // redundant next to the Breakdown panel's own date - XAxis now renders
    // `hide`.
    expect(container.querySelectorAll(".recharts-cartesian-axis-tick-value")).toHaveLength(0);
  });

  // On request: the flat single-series bar became a stacked-by-model one,
  // reusing the same categorical `.series-N` scale StackedBarPanel uses.
  // No legend (dropped on request - the hover tooltip, unchanged in shape
  // and already reading straight off each point's own `by_model`, names
  // each model on hover instead).
  it("on request: stacks each day's bar by model", () => {
    const { container } = renderWithClient(<TokensPerDayChart timeseries={TIMESERIES} />);

    // Recharts renders one `<rect>` per (category × series) regardless of
    // whether that series has data that day - a day without a model gets a
    // zero-height rect for it, not a missing one. 2026-09-24 has one model
    // (sonnet); 2026-09-25 has two (sonnet + haiku) - series-2 (haiku)
    // should be zero-height on the first day, non-zero on the second.
    const series2 = [...container.querySelectorAll(".series-2.seg")];
    expect(series2).toHaveLength(2);
    expect(Number(series2[0].getAttribute("height"))).toBe(0);
    expect(Number(series2[1].getAttribute("height"))).toBeGreaterThan(0);
  });

  // O2: click-to-drill-into-a-day.
  it("O2: reports a clicked bar's date, toggling off on a repeat click of the selected bar", () => {
    installFetchMock({});
    const onSelectDate = vi.fn();
    renderWithClient(<TokensPerDayChart timeseries={TIMESERIES} selectedDate={null} onSelectDate={onSelectDate} />);

    fireEvent.click(screen.getByTestId("chart-bar-2026-09-24"));
    expect(onSelectDate).toHaveBeenCalledWith("2026-09-24");
  });

  it("O2: clicking the already-selected bar clears the selection", () => {
    installFetchMock({});
    const onSelectDate = vi.fn();
    renderWithClient(<TokensPerDayChart timeseries={TIMESERIES} selectedDate="2026-09-24" onSelectDate={onSelectDate} />);

    fireEvent.click(screen.getByTestId("chart-bar-2026-09-24"));
    expect(onSelectDate).toHaveBeenCalledWith(null);
  });

  // On request: a zero-token day's Segment rects all render at
  // `height: 0` (nothing to click) - the testid moved onto ColumnHitArea,
  // a full-plot-height "track" rect (Recharts' `background`, sized off the
  // plot area, not this day's own value) so every day is clickable, not
  // just days with a visible bar.
  it("O2: a zero-token day is still clickable via its full-height hit area", () => {
    const zeroDay: Timeseries = {
      ...TIMESERIES,
      points: [...TIMESERIES.points, { bucket: "2026-09-26", calls: 0, tokens: 0, cost: 0, by_model: [] }],
    };
    const onSelectDate = vi.fn();
    renderWithClient(<TokensPerDayChart timeseries={zeroDay} onSelectDate={onSelectDate} selectedDate={null} />);

    // The hit area is sized off the plot area, not this day's own (zero)
    // value - non-zero height is exactly the bug this guards against.
    const hitArea = screen.getByTestId("chart-bar-2026-09-26");
    expect(Number(hitArea.getAttribute("height"))).toBeGreaterThan(0);

    fireEvent.click(hitArea);
    expect(onSelectDate).toHaveBeenCalledWith("2026-09-26");
  });

  // Regression: `cost` was missing from buildChartData's flattened row,
  // so the tooltip header's `formatCost(point.cost)` crashed on a real
  // hover (`undefined.toFixed()`) - buildSeries/tooltipRows' own tests use
  // the raw TimeseriesPoint fixture directly and never caught this, since
  // only a real hover reaches Recharts' `payload.payload`, i.e. this
  // function's actual output.
  it("carries cost onto the flattened row Recharts' Bar/Tooltip payload receives", () => {
    const series = buildSeries(TIMESERIES.points);
    const rows = buildChartData(TIMESERIES.points, series);

    expect(rows[0]).toMatchObject({ bucket: "2026-09-24", tokens: 1000, cost: 1.0 });
    expect(rows[1]).toMatchObject({ bucket: "2026-09-25", tokens: 184204, cost: 12.4 });
  });

  // On request: hover tooltip's per-model rows - each keeps its own series
  // color/order, only models actually present that day get a row, and a
  // day with fewer models than the range's full series list doesn't grow
  // extra rows for models it doesn't have.
  // The tooltip's own header date is spelled out fuller than the compact
  // "MM-DD" axis tick - a "day" bucket gets the full calendar-date label,
  // while an "hour" bucket (today's range) is already a bare time-of-day
  // and needs no change.
  describe("tooltipDateLabel", () => {
    it("spells out a 'day' bucket's date in full", () => {
      expect(tooltipDateLabel("day", "2019-01-05")).toBe("Jan 5 2019, Sat");
    });

    it("leaves an 'hour' bucket as its bare hour", () => {
      expect(tooltipDateLabel("hour", "2026-09-24T14")).toBe("14");
    });
  });

  describe("tooltipRows", () => {
    const series = buildSeries(TIMESERIES.points);

    it("lists only the day's own models, in the series' fixed order", () => {
      const day1 = tooltipRows(TIMESERIES.points[0], series);
      expect(day1.map((r) => r.key)).toEqual(["claude-sonnet-5"]);

      const day2 = tooltipRows(TIMESERIES.points[1], series);
      expect(day2.map((r) => r.key)).toEqual(["claude-sonnet-5", "claude-haiku-4.5"]);
      expect(day2[0]).toMatchObject({ seriesClass: "series-1", tokens: 150000, cost: 10.4 });
      expect(day2[1]).toMatchObject({ seriesClass: "series-2", tokens: 34204, cost: 2.0 });
    });

    it("folds models past the top 7 into one 'Other' row, summing tokens and going unknown-cost on any unpriced member", () => {
      const manyModels = Array.from({ length: 9 }, (_, i) => ({
        key: `model-${i}`,
        calls: 1,
        tokens: (9 - i) * 10, // descending, so model-0..model-6 are the top 7
        cost: i === 8 ? null : 1, // the smallest (model-8) is unpriced
      }));
      const point = { bucket: "2026-09-26", calls: 9, tokens: 450, cost: null, by_model: manyModels };
      const wideSeries = buildSeries([point]);

      const rows = tooltipRows(point, wideSeries);
      expect(rows).toHaveLength(8); // 7 named + 1 "Other"
      const other = rows[rows.length - 1];
      expect(other.label).toBe("Other");
      expect(other.tokens).toBe(20 + 10); // model-7 (20) + model-8 (10)
      expect(other.cost).toBeNull(); // model-8's unpriced cost taints the fold
    });
  });
});
