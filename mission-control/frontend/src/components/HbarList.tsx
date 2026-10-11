import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { estimateTextWidth } from "../lib/chartText";
import { ChartInfoMark } from "./ChartInfoMark";
import { TruncatedAxisTick } from "./TruncatedAxisTick";

export interface HbarRow {
  label: string;
  value: number;
  display: string;
  scope?: string;
  unknown?: boolean;
}

interface HbarListProps {
  rows: HbarRow[];
  emptyText?: string;
  maxRows?: number;
  rowTestId?: (row: HbarRow) => string;
  "data-testid"?: string;
}

const DEFAULT_MAX_ROWS = 3;
const ROW_HEIGHT = 28;

// `.hbar-row`/`.hbar-track`/`.hbar-fill` per overview-loaded.html, rebuilt
// on Recharts (goal 5) for a uniform charting library - the non-clickable
// ranked-list variant (By tool/By agent/By model, and via C7 the
// Agents-in-this-session panel). `visible`/`expanded`/`maxRows`/"Show all N
// →" is unchanged surrounding UI, not inside the chart. Each row is drawn
// by one `Bar` `shape` (see `Row` below) rather than Recharts' default
// rectangle so the bar, its value label, and its unknown-cost info-mark all
// share one `<g>` per row - `rowTestId`'s element then has the row's full
// text content as a descendant, not just an empty `<rect>`.
export function HbarList({
  rows,
  emptyText = "No data yet.",
  maxRows = DEFAULT_MAX_ROWS,
  rowTestId,
  "data-testid": testId,
}: HbarListProps) {
  const [expanded, setExpanded] = useState(false);

  if (rows.length === 0) {
    return (
      <p className="mono" style={{ color: "var(--ink-faint)", fontSize: 11.5 }}>
        {emptyText}
      </p>
    );
  }

  const visible = expanded ? rows : rows.slice(0, maxRows);
  const hiddenCount = rows.length - visible.length;
  const max = Math.max(...visible.map((r) => r.value), 1);
  const height = visible.length * ROW_HEIGHT;

  return (
    <div data-testid={testId}>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={visible} layout="vertical" margin={{ top: 0, right: 74, bottom: 0, left: 0 }} barCategoryGap={6}>
            <XAxis type="number" domain={[0, max]} hide />
            <YAxis
              type="category"
              dataKey="label"
              width={130}
              interval={0}
              tickLine={false}
              axisLine={false}
              tick={<TruncatedAxisTick />}
            />
            <Tooltip cursor={{ fill: "var(--panel-sunken)" }} content={<HbarTooltip />} />
            <Bar
              dataKey="value"
              isAnimationActive={false}
              shape={(props: unknown) => <HbarRowShape {...(props as HbarRowShapeProps)} rowTestId={rowTestId} />}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {hiddenCount > 0 && (
        <button className="btn-block" onClick={() => setExpanded(true)} data-testid={testId ? `${testId}-show-all` : undefined}>
          Show all {rows.length} →
        </button>
      )}
    </div>
  );
}

interface HbarRowShapeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  payload: HbarRow;
  rowTestId?: (row: HbarRow) => string;
}

function HbarRowShape({ x, y, width, height, payload: row, rowTestId }: HbarRowShapeProps) {
  const barHeight = Math.max(height - 9, 4);
  const barY = y + (height - barHeight) / 2;
  const cy = y + height / 2;
  const labelX = x + Math.max(width, 0) + 8;

  return (
    <g data-testid={rowTestId?.(row)}>
      <rect x={x} y={barY} width={Math.max(width, 1)} height={barHeight} rx={3} fill="var(--ink-soft)" />
      <text x={labelX} y={cy} dy={4} fontFamily="var(--mono)" fontSize={12} fontWeight={600} fill="var(--ink)">
        {row.display}
      </text>
      {row.unknown && <ChartInfoMark x={labelX + estimateTextWidth(row.display) + 6} y={cy} />}
    </g>
  );
}

function HbarTooltip({ active, payload }: { active?: boolean; payload?: { payload: HbarRow }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title mono">{row.label}</div>
      <div className="chart-tooltip-row mono">
        <span>
          {row.display}
          {row.scope ? ` · ${row.scope}` : ""}
        </span>
      </div>
      {row.unknown && <div className="chart-tooltip-row mono">Model not yet priced</div>}
    </div>
  );
}
