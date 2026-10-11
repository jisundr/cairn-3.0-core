import { useState } from "react";
import {
  useAgentRollup,
  useDayDetail,
  useModelRollup,
  useProjects,
  useSessions,
  useTimeseries,
  useToolRollup,
  useUsageLimitEvents,
} from "../api/hooks";
import type { CountRollupRow, GroupRollupRow, ProjectSummary, RangeKey, SessionSummary, UsageLimitEvent } from "../api/types";
import { AppHeader, type AppTab } from "../components/AppHeader";
import { ContributionCalendar } from "../components/ContributionCalendar";
import { isUnknownCost } from "../components/InfoDot";
import { InstallScopeRow } from "../components/InstallScopeRow";
import { Panel, PanelTitle } from "../components/Panel";
import { PanelError } from "../components/PanelError";
import { ProjectCostPanel } from "../components/ProjectCostPanel";
import { StackedBarPanel, type StackedBarRow } from "../components/StackedBarPanel";
import { StateCard } from "../components/StateCard";
import { AlertTriangleIcon, InboxIcon, RefreshIcon } from "../components/icons";
import { TokensPerDayChart } from "../components/TokensPerDayChart";
import { WarningBanner } from "../components/WarningBanner";
import { formatCost, formatDateLabel, formatRelativeToNow, formatTokens } from "../lib/format";
import { cn } from "../lib/utils";

// A view's own fixed window, not a user-facing range option - Trend keeps
// the day-by-day bar chart over the last 30 days ("30d"); Calendar's
// GitHub-style grid covers the last 13 weeks ("13w", added server-side in
// B1). Neither is offered in a shared RangeControl - this toggle replaces
// it entirely (goal: Trend/Calendar, not Today/7D/30D/Month/6M/Life).
type OverviewView = "trend" | "calendar";

const VIEW_RANGE: Record<OverviewView, RangeKey> = { trend: "30d", calendar: "13w" };
const VIEW_LABEL: Record<OverviewView, string> = { trend: "Last 30 days", calendar: "Last 13 weeks" };

// Reloading the page used to always land back on Trend (and lose the
// project filter / drilled-into day), even with one of them set - all three
// now round-trip through `?view=&project=&date=` query params (same
// hand-rolled window.location/history convention App.tsx uses for its own
// path-based routing, kept local to this in-page toggle instead).
function viewFromSearch(search: string): OverviewView {
  const param = new URLSearchParams(search).get("view");
  return param === "calendar" ? "calendar" : "trend";
}

function projectFromSearch(search: string): string | undefined {
  return new URLSearchParams(search).get("project") ?? undefined;
}

// Only a plausible YYYY-MM-DD is trusted from the URL - anything else (a
// missing param, hand-edited garbage) falls back to "no day selected"
// rather than passing through and confusing useDayDetail/sessionOverlapsDate
// downstream, both of which assume this exact shape.
function dateFromSearch(search: string): string | null {
  const param = new URLSearchParams(search).get("date");
  return param && /^\d{4}-\d{2}-\d{2}$/.test(param) ? param : null;
}

// Shared write side for all three URL-persisted toggles below - reads the
// current URL fresh each call and only touches the key(s) passed in, so
// e.g. picking a project never clobbers an already-set view or date.
function updateSearchParams(updates: Record<string, string | undefined>) {
  const params = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(updates)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

// O2: a session "falls on" a selected day if its [started, ended) window
// overlaps that UTC calendar day at all - a session spanning midnight
// counts on both days it touches, rather than only the day it started.
// ISO8601 timestamps (all `Z`-suffixed, same format) compare correctly as
// plain strings, so this needs no Date parsing.
function sessionOverlapsDate(session: SessionSummary, date: string): boolean {
  const dayStart = `${date}T00:00:00Z`;
  const dayEnd = `${date}T23:59:59.999Z`;
  return session.started <= dayEnd && session.ended >= dayStart;
}

// A usage-limit event is a point in time, not a [started, ended) window -
// same UTC-day-boundary comparison as sessionOverlapsDate above, just
// against a single timestamp instead of a range.
function eventOnDate(event: UsageLimitEvent, date: string): boolean {
  const dayStart = `${date}T00:00:00Z`;
  const dayEnd = `${date}T23:59:59.999Z`;
  return event.timestamp >= dayStart && event.timestamp <= dayEnd;
}

// O3: By models/By agents rows carry exact cost+tokens (both group rollups
// sum priced `calls` rows); By tools carries a call-count share only - see
// PLAN.md's Summary and B2's day_detail() docstring for why per-tool cost
// isn't attributable from the real schema.
function costTokenRows(rows: GroupRollupRow[]): StackedBarRow[] {
  return rows.map((r) => ({
    key: r.key,
    value: r.tokens,
    display: `${formatCost(r.cost)} (${formatTokens(r.tokens)})`,
    unknown: isUnknownCost(r.cost),
  }));
}

function callCountRows(rows: CountRollupRow[]): StackedBarRow[] {
  return rows.map((r) => ({ key: r.key, value: r.count, display: `${r.count} call${r.count === 1 ? "" : "s"}` }));
}

// Breakdown's per-row loading placeholder - the row's own name ("Cost" etc.)
// is always known immediately, only the value is pending, so this replaces
// just the "…" that used to sit where a real value renders (StackedBarPanel
// has its own three-piece skeleton for rows whose *name* is unknown too).
function ValueSkel({ width = 50 }: { width?: number }) {
  return <span className="skel" style={{ display: "inline-block", width, height: 11, verticalAlign: "middle" }} />;
}

interface OverviewProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
}

export function Overview({ activeTab, onTabChange }: OverviewProps) {
  const [view, setView] = useState<OverviewView>(() => viewFromSearch(window.location.search));
  const [projectFilter, setProjectFilter] = useState<string | undefined>(() => projectFromSearch(window.location.search));
  // O2's own drilled-into day, lifted up from OverviewLoaded so its value can
  // live in the same `?date=` query param as view/project below - still
  // reset to null whenever the view or project filter changes (a selected
  // date from a 30-day Trend window has no meaning once the window itself
  // changes shape or scope), just via these two handlers instead of an
  // effect keyed on [view, projectFilter], since that would also fire (and
  // wipe out a `?date=` restored from the URL) on the very first mount.
  const [selectedDate, setSelectedDate] = useState<string | null>(() => dateFromSearch(window.location.search));

  function handleViewChange(next: OverviewView) {
    setView(next);
    setSelectedDate(null);
    updateSearchParams({ view: next, date: undefined });
  }

  function handleProjectFilterChange(next: string | undefined) {
    setProjectFilter(next);
    setSelectedDate(null);
    updateSearchParams({ project: next, date: undefined });
  }

  function handleSelectedDateChange(next: string | null) {
    setSelectedDate(next);
    updateSearchParams({ date: next ?? undefined });
  }

  const projects = useProjects();
  const hostTag = projects.data?.hostname ?? "localhost";
  // Unscoped by range/project - answers "has backfill ever found anything,
  // for anyone" for the empty-state check below, independent of whatever
  // view/filter the page happens to be showing.
  const anyHistory = useSessions({ range: "life" });

  if (projects.isError) {
    return (
      <div className="shell">
        <AppHeader activeTab={activeTab} onTabChange={onTabChange} connected={false} showTabs={false} />
        <StateCard
          err
          data-testid="overview-disconnected"
          icon={<AlertTriangleIcon />}
          title="Can't reach the local server"
          body="The mission control server isn't responding. Your session data is safe — the Stop hook keeps capturing locally regardless."
        >
          <button className="btn-err" style={{ display: "flex", alignItems: "center", gap: 7, padding: "8px 16px" }} onClick={() => projects.refetch()}>
            <RefreshIcon size={13} />
            Retry connection
          </button>
        </StateCard>
      </div>
    );
  }

  if (anyHistory.isSuccess && anyHistory.data.length === 0) {
    return (
      <div className="shell">
        <AppHeader activeTab={activeTab} onTabChange={onTabChange} connected showTabs />
        <StateCard
          data-testid="overview-empty"
          icon={<InboxIcon />}
          title="No sessions captured yet"
          body="Backfill scanned every known project's transcript history and found nothing yet. Cairn captures a session automatically each time one ends."
        >
          <div className="state-steps">
            <div className="state-step">
              <span className="n">1</span>Work a Claude Code session in any cairn-installed project
            </div>
            <div className="state-step">
              <span className="n">2</span>Let the session end (Stop hook fires)
            </div>
            <div className="state-step">
              <span className="n">3</span>Come back and refresh
            </div>
          </div>
        </StateCard>
      </div>
    );
  }

  return (
    <OverviewLoaded
      activeTab={activeTab}
      onTabChange={onTabChange}
      hostTag={hostTag}
      projects={projects.data?.projects ?? []}
      view={view}
      onViewChange={handleViewChange}
      projectFilter={projectFilter}
      onProjectFilterChange={handleProjectFilterChange}
      selectedDate={selectedDate}
      onSelectedDateChange={handleSelectedDateChange}
    />
  );
}

interface OverviewLoadedProps {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  hostTag: string;
  projects: ProjectSummary[];
  view: OverviewView;
  onViewChange: (view: OverviewView) => void;
  projectFilter: string | undefined;
  onProjectFilterChange: (project: string | undefined) => void;
  selectedDate: string | null;
  onSelectedDateChange: (date: string | null) => void;
}

function OverviewLoaded({
  activeTab,
  onTabChange,
  hostTag,
  projects,
  view,
  onViewChange,
  projectFilter,
  onProjectFilterChange,
  selectedDate,
  onSelectedDateChange,
}: OverviewLoadedProps) {
  const range = VIEW_RANGE[view];
  const timeseries = useTimeseries({ range, project: projectFilter });
  const sessionsFiltered = useSessions({ range, project: projectFilter });
  const sessionsAllProjects = useSessions({ range });
  const toolRollup = useToolRollup({ range, project: projectFilter });
  const agentRollup = useAgentRollup({ range, project: projectFilter });
  const modelRollup = useModelRollup({ range, project: projectFilter });
  // On request: was a fixed "7d" fetch regardless of the active view, so a
  // selected date outside that window would silently filter to zero events
  // rather than showing what actually happened that day. Now scoped to the
  // same `range` every other rollup on this page uses.
  const usageLimitEvents = useUsageLimitEvents({ range, project: projectFilter });

  // O2: click-to-drill-into-a-day. `selectedDate` itself (and its reset on
  // view/project-filter change) now lives in the parent Overview component,
  // alongside view/projectFilter, so all three can share one URL-sync spot.
  const dayDetail = useDayDetail(selectedDate, projectFilter);

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  function handleRefresh() {
    timeseries.refetch();
    sessionsFiltered.refetch();
    sessionsAllProjects.refetch();
    toolRollup.refetch();
    agentRollup.refetch();
    modelRollup.refetch();
    usageLimitEvents.refetch();
    if (selectedDate) dayDetail.refetch();
    setLastUpdated(new Date());
  }

  const totalCost = selectedDate ? dayDetail.data?.total_cost ?? null : timeseries.data?.total_cost ?? null;
  const totalTokens = selectedDate ? dayDetail.data?.total_tokens ?? null : timeseries.data?.total_tokens ?? null;
  const totalsLoaded = selectedDate ? Boolean(dayDetail.data) : Boolean(timeseries.data);
  const sessionCount = selectedDate
    ? sessionsFiltered.data?.filter((s) => sessionOverlapsDate(s, selectedDate)).length ?? null
    : sessionsFiltered.data?.length ?? null;
  // Selected day, else the active view's fixed window - Breakdown and every
  // By-panel below share this same label (was two separately-computed but
  // identical expressions; collapsed to one).
  const panelLabel = selectedDate ? formatDateLabel(selectedDate) : VIEW_LABEL[view];

  // O3: By models/tools/agents - aggregate (the active range's own rollup)
  // vs. day-selected (B2's day_detail() breakdown), same source split
  // Breakdown above uses.
  const byModelsRows = costTokenRows(selectedDate ? dayDetail.data?.by_model ?? [] : modelRollup.data ?? []);
  const byModelsError = selectedDate ? dayDetail.isError : modelRollup.isError;
  const byModelsLoading = selectedDate ? !dayDetail.data : !modelRollup.data;
  const byToolsRows = callCountRows(selectedDate ? dayDetail.data?.by_tool ?? [] : toolRollup.data ?? []);
  const byToolsError = selectedDate ? dayDetail.isError : toolRollup.isError;
  const byToolsLoading = selectedDate ? !dayDetail.data : !toolRollup.data;
  const byAgentsRows = costTokenRows(selectedDate ? dayDetail.data?.by_agent ?? [] : agentRollup.data ?? []);
  const byAgentsError = selectedDate ? dayDetail.isError : agentRollup.isError;
  const byAgentsLoading = selectedDate ? !dayDetail.data : !agentRollup.data;

  // O4: By project - only on a multi-project ("system") install, same
  // `projects.length > 1` signal SessionsList.tsx already uses, and only
  // while unfiltered - once InstallScopeRow's "Project: X" chip narrows
  // the whole page to one project, a per-project breakdown has nothing
  // left to break down (on request). Reuses sessionsAllProjects (Overview's
  // own existing unfiltered fetch) rather than a new call; day-selected
  // filters that same array for date overlap before handing it to
  // ProjectCostPanel (F6) - its own projectTotals()/buildRootLabels() math
  // is unchanged either way.
  const multiProject = projects.length > 1 && !projectFilter;
  const byProjectSessions = selectedDate
    ? (sessionsAllProjects.data ?? []).filter((s) => sessionOverlapsDate(s, selectedDate))
    : sessionsAllProjects.data ?? [];

  // On request: the Breakdown row's count now tracks the selected day
  // rather than always showing the whole range's total.
  const breakdownUsageLimitEvents = selectedDate
    ? (usageLimitEvents.data ?? []).filter((e) => eventOnDate(e, selectedDate))
    : usageLimitEvents.data ?? [];

  return (
    <div className="shell">
      <AppHeader
        activeTab={activeTab}
        onTabChange={onTabChange}
        connected
        onRefresh={handleRefresh}
        updatedLabel={lastUpdated ? `updated ${formatRelativeToNow(lastUpdated.toISOString())}` : null}
      />

      <div className="range-row" data-testid="view-toggle">
        <div className="segs">
          <div className={cn("seg", view === "trend" && "active")} data-testid="view-seg-trend" onClick={() => onViewChange("trend")}>
            Trend
          </div>
          <div className={cn("seg", view === "calendar" && "active")} data-testid="view-seg-calendar" onClick={() => onViewChange("calendar")}>
            Calendar
          </div>
        </div>
      </div>

      <InstallScopeRow
        projects={projects}
        hostTag={hostTag}
        selectedProject={projectFilter}
        onSelectProject={onProjectFilterChange}
        selectedDate={selectedDate}
        onClearDate={() => onSelectedDateChange(null)}
      />

      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <Panel err={timeseries.isError} style={{ display: "flex", flexDirection: "column" }}>
          <div className="trend-panel-head">
            <PanelTitle err={timeseries.isError} style={{ margin: 0 }}>
              {view === "trend" ? "Trends" : "Daily activity"}
            </PanelTitle>
            <span className="host-name" style={{ fontWeight: 500, color: "var(--ink-faint)" }}>
              {VIEW_LABEL[view]}
            </span>
          </div>
          {timeseries.isError ? (
            <div className="err-inline">
              <PanelError message="Couldn't load — request failed" onRetry={() => timeseries.refetch()} testId="chart-error" />
            </div>
          ) : timeseries.data ? (
            view === "trend" ? (
              <TokensPerDayChart timeseries={timeseries.data} selectedDate={selectedDate} onSelectDate={onSelectedDateChange} />
            ) : (
              <ContributionCalendar points={timeseries.data.points} selectedDate={selectedDate} onSelectDate={onSelectedDateChange} />
            )
          ) : (
            <div className="skel" style={{ height: 150 }} />
          )}
        </Panel>

        <Panel style={{ display: "flex", flexDirection: "column" }}>
          <div className="trend-panel-head">
            <PanelTitle style={{ margin: 0 }}>Breakdown</PanelTitle>
            <span className="host-name" style={{ fontWeight: 500, color: "var(--ink-faint)" }}>
              {panelLabel}
            </span>
          </div>
          <div className="kv-list" data-testid="breakdown">
            <div className="kv-row" data-testid="breakdown-cost">
              <span className="name">Cost</span>
              <span className="val">{totalsLoaded ? formatCost(totalCost) : <ValueSkel />}</span>
            </div>
            <div className="kv-row" data-testid="breakdown-tokens">
              <span className="name">Tokens</span>
              <span className="val">{totalsLoaded && totalTokens !== null ? formatTokens(totalTokens) : <ValueSkel />}</span>
            </div>
            <div className="kv-row" data-testid="breakdown-sessions">
              <span className="name">Sessions</span>
              <span className="val">{sessionCount !== null ? sessionCount : <ValueSkel width={24} />}</span>
            </div>
            <WarningBanner events={breakdownUsageLimitEvents} />
          </div>
        </Panel>
      </div>

      <div className="grid grid-1">
        {multiProject && (
          <ProjectCostPanel
            sessions={byProjectSessions}
            loading={!sessionsAllProjects.data}
            projects={projects}
            selectedProject={projectFilter}
            onSelectProject={onProjectFilterChange}
          />
        )}

        <Panel err={byModelsError}>
          <div className="trend-panel-head">
            <PanelTitle err={byModelsError} style={{ margin: 0 }}>
              By models
            </PanelTitle>
            <span className="host-name" style={{ fontWeight: 500, color: "var(--ink-faint)" }}>
              {panelLabel}
            </span>
          </div>
          {byModelsError ? (
            <div className="err-inline">
              <PanelError message="Couldn't load — request failed" onRetry={() => (selectedDate ? dayDetail.refetch() : modelRollup.refetch())} testId="by-models-error" />
            </div>
          ) : (
            <StackedBarPanel data-testid="by-models" rows={byModelsRows} loading={byModelsLoading} emptyText="No model usage yet." />
          )}
        </Panel>

        <Panel err={byAgentsError}>
          <div className="trend-panel-head">
            <PanelTitle err={byAgentsError} style={{ margin: 0 }}>
              By agents
            </PanelTitle>
            <span className="host-name" style={{ fontWeight: 500, color: "var(--ink-faint)" }}>
              {panelLabel}
            </span>
          </div>
          {byAgentsError ? (
            <div className="err-inline">
              <PanelError message="Couldn't load — request failed" onRetry={() => (selectedDate ? dayDetail.refetch() : agentRollup.refetch())} testId="by-agents-error" />
            </div>
          ) : (
            <StackedBarPanel data-testid="by-agents" rows={byAgentsRows} loading={byAgentsLoading} emptyText="No agent activity yet." />
          )}
        </Panel>

        {/* On request: By tools last - was between By models and By agents. */}
        <Panel err={byToolsError}>
          <div className="trend-panel-head">
            <PanelTitle err={byToolsError} style={{ margin: 0 }}>
              By tools
            </PanelTitle>
            <span className="host-name" style={{ fontWeight: 500, color: "var(--ink-faint)" }}>
              {panelLabel}
            </span>
          </div>
          {byToolsError ? (
            <div className="err-inline">
              <PanelError message="Couldn't load — request failed" onRetry={() => (selectedDate ? dayDetail.refetch() : toolRollup.refetch())} testId="by-tools-error" />
            </div>
          ) : (
            <StackedBarPanel data-testid="by-tools" rows={byToolsRows} loading={byToolsLoading} emptyText="No tool calls yet." />
          )}
        </Panel>
      </div>
    </div>
  );
}
