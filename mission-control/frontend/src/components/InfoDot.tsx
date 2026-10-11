// `.info-dot` per overview-loaded.html - the affordance goal 3 requires
// wherever `formatCost` renders "unknown*" (an unpriced model): a small
// info icon whose `title` explains why, rather than a bare unexplained
// value.
interface InfoDotProps {
  title?: string;
}

export function InfoDot({ title = "Model not yet priced" }: InfoDotProps) {
  return (
    <span className="info-dot" title={title} data-testid="info-dot">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9.5" />
        <line x1="12" y1="11" x2="12" y2="16.5" />
        <circle cx="12" cy="7.5" r="0.75" fill="currentColor" stroke="none" />
      </svg>
    </span>
  );
}

// Shared guard: both server-side `null` (no rows found) and `"unknown"`
// (rows found, but the model isn't in prices.json) render the same
// unpriced-cost affordance. Used by every panel/table/row that renders a
// cost value from the API.
export function isUnknownCost(cost: number | "unknown" | null): boolean {
  return cost === null || cost === "unknown";
}
