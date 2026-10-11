import { Fragment, useEffect, useRef, useState } from "react";
import { useProjects, useSessions } from "../api/hooks";
import type { RangeKey, SessionSummary } from "../api/types";
import { AppHeader, type AppTab } from "../components/AppHeader";
import { InfoDot, isUnknownCost } from "../components/InfoDot";
import { InstallScopeRow } from "../components/InstallScopeRow";
import { PanelError } from "../components/PanelError";
import { RangeControl } from "../components/RangeControl";
import { InboxIcon } from "../components/icons";
import { compareVersions, formatCost, formatSessionDuration, formatStarted, shortId } from "../lib/format";

interface SessionsListProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onSelectSession: (sessionId: string) => void;
}

// S1: Session and Project aren't meaningful sort keys (an id has no order;
// Project only matters on a system install, and even there it's not what
// anyone means by "sort my sessions"). "started" is the default, matching
// the table's own prior always-newest-first order.
type SortColumn = "started" | "duration" | "tokens" | "cost";
type SortDirection = "asc" | "desc";

const SORT_COLUMNS: { value: SortColumn; label: string }[] = [
  { value: "started", label: "Started" },
  { value: "duration", label: "Duration" },
  { value: "tokens", label: "Tokens" },
  { value: "cost", label: "Cost" },
];

function sortValue(s: SessionSummary, column: SortColumn): number {
  switch (column) {
    case "started":
      return new Date(s.started).getTime();
    case "duration":
      return new Date(s.ended).getTime() - new Date(s.started).getTime();
    case "tokens":
      return s.tokens;
    case "cost":
      // An unresolved cost sorts as the lowest value in either direction,
      // rather than flipping to "highest" under desc - consistently out of
      // the way instead of swapping ends depending on sort direction.
      return s.cost ?? -Infinity;
  }
}

function sortSessions(rows: SessionSummary[], column: SortColumn, direction: SortDirection): SessionSummary[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => sign * (sortValue(a, column) - sortValue(b, column)));
}

// The newest cairn version among `rows` (the whole loaded range, not one
// page), or undefined when none has a version. A row whose version is below
// this is marked "older": it started under a plugin that has since moved on
// in this range, not necessarily older than the installed plugin.
function newestVersion(rows: SessionSummary[]): string | undefined {
  let newest: string | undefined;
  for (const s of rows) {
    const v = s.cairn_version;
    if (!v) continue;
    if (newest === undefined || compareVersions(v, newest) > 0) newest = v;
  }
  return newest;
}

// Round-trips range/project/sort/dir/page through `?range=&project=&sort=&
// dir=&page=` query params - same hand-rolled window.location/history
// convention Overview.tsx's own viewFromSearch/projectFromSearch/
// updateSearchParams use for its in-page toggles, kept local to this page.
// Anything missing or invalid falls back to today's defaults rather than
// passing through and confusing sortSessions/pagination downstream.
const RANGE_KEYS: RangeKey[] = ["today", "7d", "30d", "month", "6m", "life"];

function rangeFromSearch(search: string): RangeKey {
  const param = new URLSearchParams(search).get("range");
  return RANGE_KEYS.includes(param as RangeKey) ? (param as RangeKey) : "7d";
}

function projectFromSearch(search: string): string | undefined {
  return new URLSearchParams(search).get("project") ?? undefined;
}

function sortColumnFromSearch(search: string): SortColumn {
  const param = new URLSearchParams(search).get("sort");
  return SORT_COLUMNS.some((c) => c.value === param) ? (param as SortColumn) : "started";
}

function sortDirectionFromSearch(search: string): SortDirection {
  return new URLSearchParams(search).get("dir") === "asc" ? "asc" : "desc";
}

function pageFromSearch(search: string): number {
  const param = Number(new URLSearchParams(search).get("page"));
  return Number.isInteger(param) && param > 0 ? param : 1;
}

// Shared write side for all five URL-persisted fields above - reads the
// current URL fresh each call and only touches the key(s) passed in, so
// e.g. changing the sort column never clobbers an already-set range or page.
function updateSearchParams(updates: Record<string, string | undefined>) {
  const params = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(updates)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

// S2: Prev/Next only, no jump-to-page - a client-side slice of the
// already-fully-fetched, already-sorted array (per PLAN.md's Risks note:
// fine at this app's local single-user SQLite scale, would need revisiting
// if session counts grow well past what one /api/rollup/session call
// comfortably returns).
const PAGE_SIZE = 25;

// pages/SessionsList.tsx per sessions-list-{loaded,error,empty}.html - its
// own RangeControl instance (goal 1: Overview and Sessions List each own
// one, not a page-spanning shared control), plus (F2) the same
// InstallScopeRow Overview mounts, replacing this page's former ad-hoc
// `.segs` project-filter pill row with the shared install-type row every
// other screen in the revamp uses. S1 adds sort controls (a column
// dropdown + direction toggle, joined into one `.sort-group`, or a column-
// header click - both set the same state) over the already-fetched
// `sessions.data`, entirely client-side. S2 adds Prev/Next pagination over
// that same sorted array (resetting to page 1 on range/project/sort
// change) and drops the redundant Project column on a single-project
// install, where every row is already the same project.
export function SessionsList({ activeTab, onTabChange, onSelectSession }: SessionsListProps) {
  const [range, setRange] = useState<RangeKey>(() => rangeFromSearch(window.location.search));
  const [projectFilter, setProjectFilter] = useState<string | undefined>(() => projectFromSearch(window.location.search));
  const [sortColumn, setSortColumn] = useState<SortColumn>(() => sortColumnFromSearch(window.location.search));
  const [sortDirection, setSortDirection] = useState<SortDirection>(() => sortDirectionFromSearch(window.location.search));
  const [sortMenuOpen, setSortMenuOpen] = useState(false);
  const [page, setPage] = useState(() => pageFromSearch(window.location.search));

  const projects = useProjects();
  const hostTag = projects.data?.hostname ?? "localhost";
  const multiProject = (projects.data?.projects.length ?? 0) > 1;
  const sessions = useSessions({ range, project: projectFilter });
  const sorted = sortSessions(sessions.data ?? [], sortColumn, sortDirection);
  const newest = newestVersion(sessions.data ?? []);
  const pageStart = (page - 1) * PAGE_SIZE;
  const pageRows = sorted.slice(pageStart, pageStart + PAGE_SIZE);
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));

  // Skips its very first run - on mount, `page` already reflects whatever
  // `?page=` was restored from the URL, and this effect's own dependencies
  // (range/projectFilter/sortColumn/sortDirection) are always "new" on that
  // first render too, which would otherwise immediately reset a restored
  // deep-linked page straight back to 1 (same pitfall Overview.tsx's own
  // selectedDate-reset comment calls out for its analogous case).
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setPage(1);
  }, [range, projectFilter, sortColumn, sortDirection]);

  // Single sync point for all five URL-persisted fields - fires whenever
  // any of them change (including the page-reset above, once it takes
  // effect on the next render), so the URL's `page` param never drifts
  // from what's actually showing.
  useEffect(() => {
    updateSearchParams({
      range,
      project: projectFilter,
      sort: sortColumn,
      dir: sortDirection,
      page: String(page),
    });
  }, [range, projectFilter, sortColumn, sortDirection, page]);

  return (
    <div className="shell">
      <AppHeader
        activeTab={activeTab}
        onTabChange={onTabChange}
        connected={!projects.isError}
        onRefresh={() => {
          projects.refetch();
          sessions.refetch();
        }}
      />

      <RangeControl value={range} onChange={setRange} />

      <InstallScopeRow
        projects={projects.data?.projects ?? []}
        hostTag={hostTag}
        selectedProject={projectFilter}
        onSelectProject={setProjectFilter}
      />

      {sessions.isError ? (
        <div className="panel err" style={{ flexGrow: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <PanelError message="Couldn't load sessions — request failed" onRetry={() => sessions.refetch()} testId="sessions-error" />
          </div>
        </div>
      ) : sessions.isSuccess && sessions.data.length === 0 ? (
        <div className="panel" style={{ flexGrow: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }} data-testid="sessions-empty">
            <div className="state-icon">
              <InboxIcon />
            </div>
            <div className="state-title">No sessions in this range</div>
            <div className="state-body">Try a wider range, like 7D or Life.</div>
          </div>
        </div>
      ) : (
        <div className="panel" style={{ flexGrow: 1, display: "flex", flexDirection: "column" }}>
          <div className="panel-title" style={{ marginBottom: 8 }}>
            <span>{sessions.data ? `${sessions.data.length} sessions` : "…"}</span>
            <div className="sort-group">
              <div className="sort-select" data-testid="sort-select" onClick={() => setSortMenuOpen((o) => !o)}>
                Sort: {SORT_COLUMNS.find((c) => c.value === sortColumn)?.label}
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                {sortMenuOpen && (
                  <div className="dropdown-menu" data-testid="sort-menu">
                    {SORT_COLUMNS.map((c) => (
                      <div
                        key={c.value}
                        className="dropdown-item"
                        data-testid={`sort-option-${c.value}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSortColumn(c.value);
                          setSortMenuOpen(false);
                        }}
                      >
                        {c.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button
                type="button"
                className="sort-dir"
                data-testid="sort-direction"
                title={`Sort direction: ${sortDirection === "desc" ? "Descending" : "Ascending"} (click to toggle)`}
                onClick={() => setSortDirection((d) => (d === "desc" ? "asc" : "desc"))}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {sortDirection === "desc" ? (
                    <>
                      <path d="M12 5v14" />
                      <polyline points="19 12 12 19 5 12" />
                    </>
                  ) : (
                    <>
                      <path d="M12 19V5" />
                      <polyline points="5 12 12 5 19 12" />
                    </>
                  )}
                </svg>
              </button>
            </div>
          </div>
          <div className="table-wrap">
            <table className="sessions" data-testid="sessions-table">
              <thead>
                <tr>
                  <th>Session</th>
                  {multiProject && <th>Project</th>}
                  {SORT_COLUMNS.map((c) => (
                    <Fragment key={c.value}>
                      <th className="sortable" data-testid={`sort-header-${c.value}`} onClick={() => setSortColumn(c.value)}>
                        {c.label}
                      </th>
                      {c.value === "started" && <th>cairn</th>}
                    </Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((s) => (
                  <tr key={s.session_id} data-testid={`session-row-${s.session_id}`}>
                    <td>
                      <a className="sess" href={`/sessions/${encodeURIComponent(s.session_id)}`} onClick={(e) => {
                        e.preventDefault();
                        onSelectSession(s.session_id);
                      }}>
                        {s.label || shortId(s.session_id)}
                      </a>
                    </td>
                    {multiProject && <td>{s.project}</td>}
                    <td>{formatStarted(s.started)}</td>
                    <td data-testid={`cairn-version-${s.session_id}`}>
                      {s.cairn_version || "unknown"}
                      {s.cairn_version && newest && compareVersions(s.cairn_version, newest) < 0 && (
                        <>
                          {" "}
                          <span
                            className="kcard-kind cairn-older"
                            data-testid={`cairn-older-${s.session_id}`}
                            title={`Older than ${newest}, newest in this range`}
                          >
                            older
                          </span>
                        </>
                      )}
                    </td>
                    <td>{formatSessionDuration(s.started, s.ended)}</td>
                    <td>{s.tokens.toLocaleString()}</td>
                    <td>
                      {formatCost(s.cost)}
                      {isUnknownCost(s.cost) && <InfoDot />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span className="pg-count" data-testid="pagination-count">
              Showing {sorted.length === 0 ? 0 : pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, sorted.length)} of {sorted.length}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                type="button"
                className="pg-btn"
                data-testid="pagination-prev"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </button>
              <button
                type="button"
                className="pg-btn"
                data-testid="pagination-next"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
