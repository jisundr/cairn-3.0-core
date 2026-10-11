interface FirstLaunchBannerProps {
  scanned: number;
  total: number;
}

// `.progress-banner` per first-launch-backfilling.html - static and
// props-driven, not mounted anywhere in the real app yet (PLAN.md's
// judgment call 3). `mission-control/backfill.py` is a fire-and-forget
// daemon thread with no counters or endpoint, so there's no real
// `scanned`/`total` data source to wire this to today. This component is
// built and tested against hand-supplied props so whoever adds a
// backfill-progress capability later has a ready-made banner to mount,
// rather than a screen that's still unbuilt.
export function FirstLaunchBanner({ scanned, total }: FirstLaunchBannerProps) {
  const pct = total > 0 ? Math.round((scanned / total) * 100) : 0;

  return (
    <div className="progress-banner" data-testid="first-launch-banner">
      <div className="progress-head">
        <div className="progress-title">
          Backfilling history — {scanned} of {total} known projects scanned
        </div>
        <div className="progress-sub mono">this may take a moment on first launch</div>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
