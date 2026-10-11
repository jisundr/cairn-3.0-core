import { useMemo } from "react";
import type { TimeseriesPoint } from "../api/types";
import { formatTokens } from "../lib/format";
import { mixHex, useHeatColors } from "../lib/heatColor";

interface ContributionCalendarProps {
  points: TimeseriesPoint[];
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
}

interface Cell {
  date: string | null; // null = zero-fill (the range's own first week, before its first real day)
  tokens: number;
}

const DOW_LABELS = ["Mon", "", "Wed", "", "Fri", "", "Sun"];

// JS `Date.getUTCDay()` is 0=Sun..6=Sat - `points[].bucket` is already a
// UTC calendar date (per rollup_timeseries' own day bucketing), so this
// stays UTC too rather than mixing in the viewer's local time zone.
// Converts to a Monday-first index (0=Mon..6=Sun) for this grid's own
// Monday-aligned week columns.
function mondayIndex(dateStr: string): number {
  const dow = new Date(`${dateStr}T00:00:00Z`).getUTCDay();
  return (dow + 6) % 7;
}

// The range's own first day may fall mid-week - this grid's first column
// zero-fills (transparent, non-clickable) whatever days precede it, the
// same convention GitHub's own contribution graph uses.
function buildWeeks(points: TimeseriesPoint[]): Cell[][] {
  if (points.length === 0) return [];
  const cells: Cell[] = points.map((p) => ({ date: p.bucket, tokens: p.tokens }));
  const leading: Cell[] = Array.from({ length: mondayIndex(cells[0].date as string) }, () => ({ date: null, tokens: 0 }));
  const allCells = [...leading, ...cells];

  const weeks: Cell[][] = [];
  for (let i = 0; i < allCells.length; i += 7) {
    const week = allCells.slice(i, i + 7);
    while (week.length < 7) week.push({ date: null, tokens: 0 });
    weeks.push(week);
  }
  return weeks;
}

// `.cal-*` per the overview-revamp mockups' Calendar view - a GitHub-style
// contribution heatmap (weeks as columns, Monday-aligned rows) replacing
// Trend's day-by-day bar chart. Colors use a continuous `--add` intensity
// scale (F1's lib/heatColor.ts, this component's only consumer now that
// the hour-of-day ActivityHeatmap it was shared with is gone) rather than a
// second, discrete color system. No "today" indicator (dropped on
// request). Clicking a cell reports its date via `onSelectDate`, toggling
// off on a repeat click of the already-selected cell; zero-filled cells
// aren't clickable at all (there's no date behind them).
export function ContributionCalendar({ points, selectedDate, onSelectDate }: ContributionCalendarProps) {
  const colors = useHeatColors();
  const weeks = useMemo(() => buildWeeks(points), [points]);
  const max = Math.max(...points.map((p) => p.tokens), 0);

  return (
    <div data-testid="contribution-calendar">
      <div className="cal-body">
        <div className="cal-daylabels">
          {DOW_LABELS.map((label, i) => (
            <div key={i}>{label}</div>
          ))}
        </div>
        <div className="cal-scroll">
          <div className="cal-grid">
            {weeks.map((week, wi) => (
              <div className="cal-week" key={wi}>
                {week.map((cell, di) => {
                  if (cell.date === null) {
                    return <div className="cal-cell zerofill" key={di} />;
                  }
                  const opacity = max === 0 || cell.tokens === 0 ? 0 : Math.max(0.15, cell.tokens / max);
                  const isSelected = cell.date === selectedDate;
                  return (
                    <div
                      key={di}
                      className={`cal-cell${isSelected ? " selected" : ""}`}
                      style={{ background: mixHex(colors.border, colors.add, opacity) }}
                      title={`${cell.date} — ${formatTokens(cell.tokens)} tokens`}
                      data-testid={`cal-cell-${cell.date}`}
                      onClick={() => onSelectDate(isSelected ? null : cell.date)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="cal-legend">
        <span className="lbl">Less</span>
        <span className="sw" style={{ background: "var(--border-soft)" }} />
        <span className="sw" style={{ background: mixHex(colors.border, colors.add, 0.35) }} />
        <span className="sw" style={{ background: mixHex(colors.border, colors.add, 0.6) }} />
        <span className="sw" style={{ background: mixHex(colors.border, colors.add, 0.85) }} />
        <span className="sw" style={{ background: colors.add }} />
        <span className="lbl">More</span>
      </div>
    </div>
  );
}
