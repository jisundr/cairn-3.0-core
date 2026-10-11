import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Timeseries, TimeseriesPoint } from "../api/types";
import { formatCost, formatDateLabel, formatDayLabel, formatTokens } from "../lib/format";
import { isUnknownCost } from "./InfoDot";

interface TokensPerDayChartProps {
  timeseries: Timeseries;
  // O2: click-to-drill-into-a-day. Both optional - a caller that never
  // passes them (none currently do) gets the plain hover-tooltip chart
  // this component always was, no click behavior added.
  selectedDate?: string | null;
  onSelectDate?: (date: string | null) => void;
}

// Matches design.css's --series-1..8 categorical scale (dataviz skill's
// validated default) - StackedBarPanel's own scale, reused here so a model
// keeps the same color across every panel it shows up in. More than 8
// distinct models across the visible range fold into one "Other" slot
// (series 8) rather than cycling a hue onto a second model - never color
// two different identities the same.
const SERIES_COUNT = 8;
const OTHER_KEY = "__other__";

interface Series {
  key: string;
  label: string;
  seriesClass: string;
}

// Fixed hue order across the whole range: descending by each model's total
// tokens (ties broken by first appearance) - same sort rollup_group/B1's
// per-bucket by_model already applies, just summed across buckets first.
// Exported for direct unit tests of the fold/aggregate logic - Recharts'
// hover-driven Tooltip is real-browser territory (jsdom can't reliably
// reproduce its internal hit-testing), so those live in this function and
// `tooltipRows` rather than a simulated-hover DOM test.
export function buildSeries(points: TimeseriesPoint[]): Series[] {
  const totals = new Map<string, number>();
  for (const p of points) {
    for (const m of p.by_model) totals.set(m.key, (totals.get(m.key) ?? 0) + m.tokens);
  }
  const ranked = [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([key]) => key);

  const keys = ranked.length <= SERIES_COUNT ? ranked : [...ranked.slice(0, SERIES_COUNT - 1), OTHER_KEY];
  return keys.map((key, i) => ({ key, label: key === OTHER_KEY ? "Other" : key, seriesClass: `series-${i + 1}` }));
}

interface TooltipRow {
  key: string;
  label: string;
  seriesClass: string;
  tokens: number;
  cost: number | null;
}

// Same fold as buildChartData (a model outside the top series joins
// "Other"), so the tooltip's rows always match what the stack itself
// visually shows for that day - never lists a model the bar doesn't have
// its own color for. Only models present that day get a row (no $0.00
// placeholders); order follows `series`' fixed hue order.
export function tooltipRows(point: TimeseriesPoint, series: Series[]): TooltipRow[] {
  const known = new Set(series.filter((s) => s.key !== OTHER_KEY).map((s) => s.key));
  const other = series.find((s) => s.key === OTHER_KEY);
  const byKey = new Map<string, TooltipRow>();
  for (const m of point.by_model) {
    const target = known.has(m.key) ? series.find((s) => s.key === m.key)! : other!;
    const existing = byKey.get(target.key);
    if (existing) {
      existing.tokens += m.tokens;
      existing.cost = existing.cost === null || m.cost === null ? null : existing.cost + m.cost;
    } else {
      byKey.set(target.key, { key: target.key, label: target.label, seriesClass: target.seriesClass, tokens: m.tokens, cost: m.cost });
    }
  }
  return series.filter((s) => byKey.has(s.key)).map((s) => byKey.get(s.key)!);
}

// One row per bucket, each series' token share as its own numeric field -
// Recharts' stacked `<Bar dataKey>` convention needs the value addressable
// directly on the data row, not nested in `by_model`.
// Exported alongside buildSeries/tooltipRows - this is what Recharts' Bar
// `payload` and the Tooltip's hovered row actually receive, so a field the
// tooltip reads (e.g. `cost`) but this function forgets to carry over is a
// real runtime crash (`undefined.toFixed()` inside formatCost/formatTokens)
// that only a real hover, not buildSeries/tooltipRows' own unit tests,
// would have caught - test this shape directly instead of only reaching it
// via a simulated hover.
export function buildChartData(points: TimeseriesPoint[], series: Series[]): Record<string, unknown>[] {
  const known = new Set(series.map((s) => s.key).filter((k) => k !== OTHER_KEY));
  return points.map((p) => {
    const row: Record<string, unknown> = { bucket: p.bucket, tokens: p.tokens, cost: p.cost, by_model: p.by_model };
    for (const s of series) row[s.key] = 0;
    for (const m of p.by_model) {
      const target = known.has(m.key) ? m.key : OTHER_KEY;
      if (target in row) row[target] = (row[target] as number) + m.tokens;
    }
    return row;
  });
}

// `.chart-bars` per overview-loaded.html, rebuilt on Recharts (goal 3), one
// stacked column per `Timeseries` point (on request - was a single flat
// bar) - each series is a model, drawn via a custom `Bar` `shape`
// (`Segment` below) rather than Recharts' deprecated `<Cell>`, the same
// convention every other clickable/test-id-bearing bar/cell in this app
// uses (`<Cell>` forwards neither a click handler nor `data-testid`).
// Per-model tokens now come straight off each point's own `by_model` (B1) -
// no more per-hover `useDayDetail` fetch, since the whole range's
// breakdown is already loaded. No "today" indicator (dropped on request) -
// a selected day (O2) gets an outline on every one of its segments.
export function TokensPerDayChart({ timeseries, selectedDate, onSelectDate }: TokensPerDayChartProps) {
  const points = timeseries.points;
  const series = buildSeries(points);
  const data = buildChartData(points, series);

  return (
    <div data-testid="chart-bars" style={{ width: "100%", height: 150 }}>
      <ResponsiveContainer width="100%" height={150}>
        <BarChart data={data}>
          <XAxis dataKey="bucket" hide />
          <YAxis hide domain={[0, "auto"]} />
          <Tooltip
            cursor={{ fill: "var(--panel-sunken)" }}
            content={({ active, payload }) => {
              const point = payload?.[0]?.payload as (TimeseriesPoint & { bucket: string }) | undefined;
              if (!active || !point) return null;
              return <DayTooltip point={point} dateLabel={tooltipDateLabel(timeseries.bucket, point.bucket)} series={series} />;
            }}
          />
          {series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              stackId="tokens"
              isAnimationActive={false}
              maxBarSize={30}
              // On request: a day with zero tokens rendered every segment at
              // `height:0` - nothing to click. `background` is Recharts' own
              // mechanism for a full-plot-height "track" rect per category,
              // sized independently of that category's own value - set on
              // the baseline series only (one is enough), it's what makes
              // every day clickable, not just days with a visible bar. It
              // also now carries the stable per-day testid, since it's the
              // one element guaranteed to render (and be non-zero-sized) for
              // every day regardless of which models that day has.
              background={
                i === 0
                  ? (props: unknown) => (
                      <ColumnHitArea {...(props as ColumnHitAreaProps)} selectedDate={selectedDate} onSelectDate={onSelectDate} />
                    )
                  : undefined
              }
              shape={(props: unknown) => (
                <Segment {...(props as SegmentShapeProps)} seriesClass={s.seriesClass} selectedDate={selectedDate} onSelectDate={onSelectDate} />
              )}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface SegmentShapeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  payload: TimeseriesPoint & { bucket: string };
  seriesClass: string;
  selectedDate: string | null | undefined;
  onSelectDate: ((date: string | null) => void) | undefined;
}

function Segment({ x, y, width, height, payload: point, seriesClass, selectedDate, onSelectDate }: SegmentShapeProps) {
  const date = bucketDate(point.bucket);
  const selected = date === selectedDate;

  return (
    <rect
      x={x}
      y={y}
      width={Math.max(width, 1)}
      height={Math.max(height, 0)}
      rx={2}
      className={`seg ${seriesClass}${selected ? " selected" : ""}`}
      style={{ cursor: onSelectDate ? "pointer" : undefined }}
      onClick={onSelectDate ? () => onSelectDate(selected ? null : date) : undefined}
    />
  );
}

interface ColumnHitAreaProps {
  x: number;
  y: number;
  width: number;
  height: number;
  payload: TimeseriesPoint & { bucket: string };
}

function ColumnHitArea({
  x,
  y,
  width,
  height,
  payload: point,
  selectedDate,
  onSelectDate,
}: ColumnHitAreaProps & { selectedDate: string | null | undefined; onSelectDate: ((date: string | null) => void) | undefined }) {
  const date = bucketDate(point.bucket);
  const selected = date === selectedDate;

  return (
    <rect
      x={x}
      y={y}
      width={Math.max(width, 1)}
      height={Math.max(height, 0)}
      fill="transparent"
      style={{ cursor: onSelectDate ? "pointer" : undefined }}
      data-testid={`chart-bar-${date}`}
      onClick={onSelectDate ? () => onSelectDate(selected ? null : date) : undefined}
    />
  );
}

function bucketDate(bucket: string): string {
  // "day" buckets are already "YYYY-MM-DD"; "hour" buckets ("today"'s range)
  // are "YYYY-MM-DDTHH" - useDayDetail's /api/rollup/day-detail wants the
  // plain date either way.
  return bucket.slice(0, 10);
}

function tickLabel(bucket: "hour" | "day", value: string): string {
  return bucket === "hour" ? value.slice(-2) : formatDayLabel(value);
}

// Tooltip's own header date - the terser "MM-DD" tickLabel above is meant
// for an axis tick, not spelled out enough for the tooltip's date line;
// "hour" buckets are already a bare time-of-day, so keep tickLabel's answer
// there and only swap in the fuller format for "day" buckets. Exported for
// direct unit test, same reasoning as buildSeries/tooltipRows: a real hover
// is real-browser territory jsdom can't reliably reproduce.
export function tooltipDateLabel(bucket: "hour" | "day", value: string): string {
  return bucket === "day" ? formatDateLabel(bucketDate(value)) : tickLabel(bucket, value);
}

// On request: date + day total on their own header row (cost first, tokens
// parenthetical - same "$X (Y tok)" order the By-panels already use), then
// one row per model with its own color swatch + name on the left and its
// own cost(tokens) on the right - a miniature of a By-models panel row
// rather than the plain two-column text list this used to be.
function DayTooltip({
  point,
  dateLabel,
  series,
}: {
  point: TimeseriesPoint & { bucket: string };
  dateLabel: string;
  series: Series[];
}) {
  const rows = tooltipRows(point, series);
  return (
    <div className="chart-tooltip chart-tooltip-day">
      <div className="chart-tooltip-title mono" style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <span>{dateLabel}</span>
        <span>
          {formatCost(point.cost)} ({formatTokens(point.tokens)})
        </span>
      </div>
      {rows.map((row) => (
        <div className="chart-tooltip-row mono" key={row.key}>
          <span style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
            <span className={`sw ${row.seriesClass}`} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.label}</span>
          </span>
          <span style={{ flexShrink: 0 }}>
            {formatCost(row.cost)} ({formatTokens(row.tokens)})
            {isUnknownCost(row.cost) ? " (unpriced)" : ""}
          </span>
        </div>
      ))}
    </div>
  );
}
