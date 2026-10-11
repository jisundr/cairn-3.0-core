import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { InfoDot } from "./InfoDot";

export interface StackedBarRow {
  key: string;
  value: number;
  display: string;
  unknown?: boolean;
}

interface StackedBarPanelProps {
  rows: StackedBarRow[];
  // True while the caller's rollup query hasn't resolved yet - `rows` is
  // indistinguishable from "genuinely empty" otherwise (both `[]`), which
  // flashed the empty-text message during every load. Skeleton wins over
  // `rows.length === 0` regardless of what `rows` currently holds.
  loading?: boolean;
  emptyText?: string;
  "data-testid"?: string;
  // Optional click-to-filter (F6's ProjectCostPanel restyle is this
  // component's first interactive consumer - By models/tools/agents (O3)
  // stay non-interactive by simply not passing these). The caller owns
  // toggle-off-on-repeat-click logic; this component only reports which
  // row's legend was clicked.
  onSelectRow?: (key: string) => void;
  selectedKey?: string;
  rowTestId?: (row: StackedBarRow) => string;
}

// Matches design.css's --series-1..8 categorical scale (dataviz skill's
// validated default, fixed hue order - CVD-safe for the adjacent pairs a
// stacked bar puts on screen). A row's color is its position, not its
// identity, so more than 8 rows would repeat a hue - none of By
// models/tools/agents/project currently return that many.
const SERIES_COUNT = 8;

// `.stackbar`/`.seg`/`.stack-legend` per the overview-revamp mockups' By
// models/tools/agents/project panels - one proportional segmented Recharts
// stacked BarChart (a single category, one <Bar stackId> per row) plus a
// legend row per entry (swatch/name/display), on the categorical `.series-N`
// scale. Which rows/values it's handed (range-wide aggregate vs. a single
// selected day) is a decision each Overview panel (O3/O4) makes, not this
// component's own state.
export function StackedBarPanel({
  rows,
  loading = false,
  emptyText = "No data yet.",
  "data-testid": testId,
  onSelectRow,
  selectedKey,
  rowTestId,
}: StackedBarPanelProps) {
  if (loading) {
    return (
      <div data-testid={testId ? `${testId}-loading` : undefined}>
        <div className="skel" style={{ height: 10, borderRadius: 5 }} />
        <div className="stack-legend">
          {/* Same three-piece row shape as a real `.item` (swatch, name,
              right-aligned value) - a plain shrinking bar per row read as a
              different layout entirely (no swatch, no right-aligned value). */}
          {[38, 30, 34].map((nameWidth, i) => (
            <div className="item" key={i}>
              <span className="skel" style={{ width: 8, height: 8, borderRadius: 2, flexShrink: 0 }} />
              <span className="skel" style={{ height: 11, width: `${nameWidth}%` }} />
              <span className="skel" style={{ height: 11, width: 44, marginLeft: "auto", flexShrink: 0 }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <p className="mono" style={{ color: "var(--ink-faint)", fontSize: 11.5 }}>
        {emptyText}
      </p>
    );
  }

  // An all-unresolved-cost row set (every row's `value` forced to 0 by its
  // caller, e.g. ProjectCostPanel's unknown-cost projects) sums to 0 - the
  // explicit `|| 1` domain fallback below keeps that a valid (if invisible)
  // zero-width stack rather than a degenerate [0, 0] axis domain, same "no
  // visible bar, but the legend row still shows" behavior as before.
  const total = rows.reduce((sum, r) => sum + r.value, 0);
  // Recharts stacks one <Bar> per row onto a single category ("row") in
  // declaration order - one-item `data` array keyed by each row's own key.
  // `row` is the YAxis category dataKey below - its band scale needs a real
  // field to key off, even though the axis itself renders hidden.
  const data = [{ row: "total", ...Object.fromEntries(rows.map((r) => [r.key, r.value])) }];

  return (
    <div data-testid={testId}>
      <div className="stackbar">
        <ResponsiveContainer width="100%" height={10}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }} barCategoryGap={0}>
            <XAxis type="number" hide domain={[0, total || 1]} />
            <YAxis type="category" dataKey="row" hide />
            {rows.map((row, i) => (
              <Bar
                key={row.key}
                dataKey={row.key}
                stackId="stack"
                isAnimationActive={false}
                shape={(props: unknown) => (
                  <Segment
                    {...(props as SegmentShapeProps)}
                    seriesClass={`series-${(i % SERIES_COUNT) + 1}`}
                    isFirst={i === 0}
                    isLast={i === rows.length - 1}
                    selected={row.key === selectedKey}
                    testId={testId ? `${testId}-seg-${row.key}` : undefined}
                  />
                )}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="stack-legend">
        {rows.map((row, i) => (
          <div
            className={`item${onSelectRow ? " clickable" : ""}${row.key === selectedKey ? " selected" : ""}`}
            key={row.key}
            data-testid={rowTestId ? rowTestId(row) : testId ? `${testId}-legend-${row.key}` : undefined}
            onClick={onSelectRow ? () => onSelectRow(row.key) : undefined}
          >
            <span className={`sw series-${(i % SERIES_COUNT) + 1}`} />
            <span className="name">{row.key}</span>
            <span className="val">{row.display}</span>
            {row.unknown && <InfoDot />}
          </div>
        ))}
      </div>
    </div>
  );
}

interface SegmentShapeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  seriesClass: string;
  isFirst: boolean;
  isLast: boolean;
  selected: boolean;
  testId: string | undefined;
}

// A segment's own rect, inset by the dataviz skill's 2px surface gap on
// whichever side(s) touch a neighboring segment (none on the outer edges,
// which take the skill's 4px rounded data-end instead - `rx` applied
// uniformly is fine at this height, since the inner corner it also rounds
// is masked by the adjacent segment's gap).
function Segment({ x, y, width, height, seriesClass, isFirst, isLast, selected, testId }: SegmentShapeProps) {
  const GAP = 2;
  const insetLeft = isFirst ? 0 : GAP / 2;
  const insetRight = isLast ? 0 : GAP / 2;
  return (
    <rect
      x={x + insetLeft}
      y={y}
      width={Math.max(width - insetLeft - insetRight, 0)}
      height={height}
      rx={isFirst || isLast ? 4 : 0}
      className={`seg ${seriesClass}${selected ? " selected" : ""}`}
      data-testid={testId}
    />
  );
}
