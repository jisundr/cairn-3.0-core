// Shared Recharts `tick` renderer (the shape its `YAxis`/`XAxis` `tick` prop
// accepts - a component receiving `{ x, y, payload }`) for HbarList,
// ProjectCostPanel, and (via HbarList) Drilldown's agent panel. Replaces the
// fixed-width `.hbar-label` div (goal 6): a long label (e.g.
// "impeccable:impeccable-finish-reviewer") truncates with an ellipsis
// instead of colliding with the bar or the value column, and an SVG
// `<title>` carries the full name on hover, exactly like the native HTML
// `title` this rebuild replaces would give.
const MAX_CHARS = 18;

interface TickPayload {
  value: string;
}

interface TruncatedAxisTickProps {
  x?: number;
  y?: number;
  payload?: TickPayload;
}

export function TruncatedAxisTick({ x = 0, y = 0, payload }: TruncatedAxisTickProps) {
  const value = payload?.value ?? "";
  const truncated = value.length > MAX_CHARS ? `${value.slice(0, MAX_CHARS - 1)}…` : value;

  return (
    <g>
      <title>{value}</title>
      <text x={x} y={y} dy={4} textAnchor="end" fontFamily="var(--mono)" fontSize={12} fill="var(--ink)">
        {truncated}
      </text>
    </g>
  );
}
