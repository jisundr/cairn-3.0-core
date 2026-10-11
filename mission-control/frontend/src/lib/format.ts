export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}k`;
  return String(n);
}

export function formatCost(cost: number | "unknown" | null): string {
  if (cost === null || cost === "unknown") return "unknown";
  return `$${cost.toFixed(2)}`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  return `${seconds.toFixed(1)}s`;
}

export function formatTimeOfDay(iso: string): string {
  // ISO strings from server.py are UTC ("...Z"); Date's local-time getters
  // render the viewer's own time zone, which the browser already knows.
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function formatDayLabel(dateStr: string): string {
  // dateStr: "YYYY-MM-DD"
  const [, month, day] = dateStr.split("-");
  return `${month}-${day}`;
}

// Readable form of a "YYYY-MM-DD" calendar day, e.g. "Sep 28, Mon" for the
// current year, or "Jan 5 2019, Sat" for a past/future year. Parsed and
// formatted as a UTC calendar date (not local time) so the displayed date
// always matches the literal input regardless of the viewer's time zone -
// same UTC-day convention as Overview's sessionOverlapsDate/eventOnDate
// day-boundary checks. `now` defaults to the real clock but is injectable
// so "is this the current year" is testable without depending on it.
export function formatDateLabel(dateStr: string, now: Date = new Date()): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(Date.UTC(year, month - 1, day));
  const monthName = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  const weekday = d.toLocaleString("en-US", { weekday: "short", timeZone: "UTC" });
  const yearPart = year === now.getUTCFullYear() ? "" : ` ${year}`;
  return `${monthName} ${d.getUTCDate()}${yearPart}, ${weekday}`;
}

// Fallback label for a session with no saved title yet (parser.py found no
// "ai-title" record) - first 8 chars of the session's full UUID, matching
// the mockup's `a8de42…c884`-style short id.
export function shortId(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 6)}…${id.slice(-4)}`;
}

export function formatStarted(iso: string): string {
  const d = new Date(iso);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hh}:${mm}`;
}

// Session-total runtime ("41m", "1h 05m") - mm:ss/h:mm reads better than
// formatDuration's decimal-seconds form (built for the ~seconds-long call
// rows in a Drilldown) once a session runs to minutes or hours.
export function formatSessionDuration(startIso: string, endIso: string): string {
  const totalSeconds = Math.max(0, (new Date(endIso).getTime() - new Date(startIso).getTime()) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${Math.round(totalSeconds)}s`;
}

// Kanban card title (PRD §6.1/§6.3): `/api/tasks`' `folder` is a full
// relative path (e.g. "docs/tasks/2026-09-28-1345-build-kanban-board") for
// a top-level task, or the same shape ending in a sub-task's own
// "0N-<kind>-slug" for a child - the approved mockups show neither the
// "docs/tasks/" prefix nor a top-level folder's own "YYYY-MM-DD-HHMM-"
// date/time prefix (e.g. "build-kanban-board", not the folder's literal
// name), while a sub-task's "0N-..." numbering stays as-is (it never had a
// date prefix to strip). Basename first, then strip that one prefix shape.
export function taskDisplayName(folder: string): string {
  const basename = folder.split("/").pop() ?? folder;
  return basename.replace(/^\d{4}-\d{2}-\d{2}-\d{4}-/, "");
}

const DAY_MS = 24 * 60 * 60 * 1000;
const LAST_TOUCHED_SKEW_MS = 5 * 60 * 1000;

export function formatLastTouched(lastLogDate: string, lastLogTime: string, now: Date = new Date()): string {
  if (!lastLogTime) return formatDateLabel(lastLogDate, now);
  const diffMs = now.getTime() - new Date(`${lastLogDate}T${lastLogTime}:00Z`).getTime();
  // Beyond the skew allowance a future stamp (e.g. a local-time line read as
  // UTC) is untrustworthy, so show the date rather than "0s ago".
  if (diffMs < -LAST_TOUCHED_SKEW_MS) return formatDateLabel(lastLogDate, now);
  if (diffMs >= DAY_MS) return `${Math.floor(diffMs / DAY_MS)}d ago`;
  return formatRelativeToNow(`${lastLogDate}T${lastLogTime}:00Z`, now);
}

// A drawer Activity stamp: relative time for a single-day entry that has a
// time (log times are UTC), else the raw date or range as the log wrote it.
export function formatActivityStamp(date: string, time: string | null, now: Date = new Date()): string {
  if (time && /^\d{4}-\d{2}-\d{2}$/.test(date)) return formatLastTouched(date, time, now);
  return date;
}

export function formatRelativeToNow(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  const diffMs = now.getTime() - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${Math.max(0, diffSec)}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  return `${diffHr}h ago`;
}

// The cairn version a session started under, for display. A session with
// none recorded (it predates version capture, or its log line was unreadable)
// reads "cairn unknown".
export function formatCairnVersion(version: string | null | undefined): string {
  return `cairn ${version || "unknown"}`;
}

const VERSION_CORE_RE = /^(\d+)\.(\d+)\.(\d+)/;

// Orders two cairn versions by numeric major.minor.patch (negative when `a`
// is older). Any -/+ suffix is ignored, and input that doesn't start with a
// major.minor.patch triple compares equal to anything, so it never ranks.
export function compareVersions(a: string, b: string): number {
  const ma = VERSION_CORE_RE.exec(a);
  const mb = VERSION_CORE_RE.exec(b);
  if (!ma || !mb) return 0;
  for (let i = 1; i <= 3; i++) {
    const diff = Number(ma[i]) - Number(mb[i]);
    if (diff !== 0) return diff;
  }
  return 0;
}
