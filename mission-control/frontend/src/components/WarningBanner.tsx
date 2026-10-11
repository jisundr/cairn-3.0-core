import type { UsageLimitEvent } from "../api/types";

interface WarningBannerProps {
  events: UsageLimitEvent[];
}

// Kept from token-metering/frontend, restyled to this design system - no
// mockup shows it (none of the 10 states hit a usage-limit event) and
// DESIGN.md doesn't name it, but `/api/usage-limit-events` is unchanged v1
// API surface; dropping a working feature silently would be a bigger
// change than a mockup simply omitting an edge case (see PLAN.md's
// judgment call 2). On request, moved from a standalone top-of-page alert
// box into a `.kv-row` inside Breakdown - same conditional-render behavior
// (nothing renders when the caller's events are empty), same name:value
// shape as Cost/Tokens/Sessions above it. On request, no longer a link to
// the most recent event's session - the caller (Overview) is responsible
// for handing this component whichever events are in scope (the active
// range, or just a selected day - see Overview.tsx's `eventOnDate`).
export function WarningBanner({ events }: WarningBannerProps) {
  if (events.length === 0) return null;

  const plural = events.length === 1 ? "once" : `${events.length} times`;

  return (
    <div
      className="kv-row"
      data-testid="usage-limit-banner"
      style={{ borderTop: "1px solid var(--border-soft)", marginTop: 2, paddingTop: 8 }}
    >
      <span className="name" style={{ color: "var(--remove)" }}>
        Usage limit
      </span>
      <span className="val" style={{ color: "var(--remove)" }}>
        {plural}
      </span>
    </div>
  );
}
