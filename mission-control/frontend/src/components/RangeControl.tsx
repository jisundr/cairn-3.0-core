import type { RangeKey } from "../api/types";
import { cn } from "../lib/utils";

const RANGE_OPTIONS: { value: RangeKey; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "7d", label: "7D" },
  { value: "30d", label: "30D" },
  { value: "month", label: "Month" },
  { value: "6m", label: "6M" },
  { value: "life", label: "Life" },
];

interface RangeControlProps {
  value: RangeKey;
  onChange: (range: RangeKey) => void;
}

// `.range-row` per overview-loaded.html - one shared instance per page
// (Overview and Sessions List each own their own instance) drives every
// panel that reads range-scoped data on that page, replacing each panel's
// former independent range state.
export function RangeControl({ value, onChange }: RangeControlProps) {
  return (
    <div className="range-row" data-testid="range-control">
      <span className="range-label">Range</span>
      <div className="segs">
        {RANGE_OPTIONS.map((opt) => (
          <div
            key={opt.value}
            className={cn("seg", value === opt.value && "active")}
            role="button"
            tabIndex={0}
            data-testid={`range-seg-${opt.value}`}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onChange(opt.value);
            }}
          >
            {opt.label}
          </div>
        ))}
      </div>
    </div>
  );
}
