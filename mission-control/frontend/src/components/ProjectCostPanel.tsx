import type { ProjectSummary, SessionSummary } from "../api/types";
import { formatCost } from "../lib/format";
import { InfoDot, isUnknownCost } from "./InfoDot";
import { Panel, PanelTitle } from "./Panel";
import { StackedBarPanel, type StackedBarRow } from "./StackedBarPanel";

interface ProjectTotal {
  label: string;
  cost: number | "unknown";
}

// Goal 8: a project's own label maps to its ultimate ancestor's label
// (walking `parent` per `/api/projects`, added server-side in C1/C10) -
// e.g. both `engine` and `site` map to `ai-worth-carrying`, their filesystem
// parent, which then carries their sessions' cost in its own row instead of
// each showing as an independent top-level project. A cycle (which
// `discover_projects()` should never itself produce, but this walk doesn't
// assume that) stops after `projects.length` hops rather than looping
// forever, falling back to the project's own label. Also the fallback when
// `projects` is empty or still loading, or a session's `project` isn't in
// it at all (a label `sessions` mentions that the current `/api/projects`
// fetch doesn't, however that might happen) - a session's own label is
// always at least as good a bucket as dropping it.
function buildRootLabels(projects: ProjectSummary[]): Map<string, string> {
  const byLabel = new Map(projects.map((p) => [p.label, p]));
  const maxHops = projects.length;
  const roots = new Map<string, string>();
  for (const project of projects) {
    let current = project;
    let hops = 0;
    while (current.parent !== null && byLabel.has(current.parent) && hops < maxHops) {
      current = byLabel.get(current.parent)!;
      hops += 1;
    }
    roots.set(project.label, current.label);
  }
  return roots;
}

// Goal 4's fix: sums each project's **cost**, not tokens, and renders even
// for a single-project install (today's ProjectsPanel.tsx sums tokens and
// is gated `multiProject &&`, hidden entirely below 2 projects). There's
// still no dedicated per-project rollup endpoint, so this sums client-side
// from the already-fetched session rollup - but a project total is only
// ever shown as a real number when *every* contributing session has a
// priced cost; one `null`-cost session marks the whole project "unknown"
// (with goal 3's info-mark) rather than silently coercing that session's
// cost to zero and understating the total. `rootLabels` (goal 8) buckets
// each session under its root label rather than its own `project`, so a
// root with no sessions of its own but children with sessions still gets a
// row - the bucket exists because a child mapped into it.
function projectTotals(sessions: SessionSummary[], rootLabels: Map<string, string>): ProjectTotal[] {
  const rootLabel = (project: string) => rootLabels.get(project) ?? project;
  const sums = new Map<string, number>();
  const unresolved = new Set<string>();
  for (const s of sessions) {
    const label = rootLabel(s.project);
    if (s.cost === null) {
      unresolved.add(label);
      continue;
    }
    sums.set(label, (sums.get(label) ?? 0) + s.cost);
  }
  const labels = new Set([...sums.keys(), ...unresolved]);
  return [...labels]
    .map((label): ProjectTotal => (unresolved.has(label) ? { label, cost: "unknown" } : { label, cost: sums.get(label) ?? 0 }))
    .sort((a, b) => {
      if (a.cost === "unknown" && b.cost === "unknown") return a.label.localeCompare(b.label);
      if (a.cost === "unknown") return 1;
      if (b.cost === "unknown") return -1;
      return b.cost - a.cost;
    });
}

interface ProjectCostPanelProps {
  sessions: SessionSummary[];
  loading?: boolean;
  projects: ProjectSummary[];
  selectedProject: string | undefined;
  onSelectProject: (project: string | undefined) => void;
}

function toStackedBarRows(totals: ProjectTotal[]): StackedBarRow[] {
  return totals.map((t) => ({
    key: t.label,
    value: t.cost === "unknown" ? 0 : t.cost,
    display: formatCost(t.cost),
    unknown: isUnknownCost(t.cost),
  }));
}

// `By project` per the overview-revamp mockups (F6) - restyled onto
// StackedBarPanel (F5), keeping `projectTotals`/`buildRootLabels`'s own
// per-project cost math and click-to-filter behavior unchanged (only the
// rendering swapped, from a Recharts `BarChart` to the shared stacked-bar
// visual every other By-panel now uses). Toggle-off-on-repeat-click still
// lives here, not in StackedBarPanel: clicking the already-selected
// project's legend row clears the filter.
export function ProjectCostPanel({ sessions, loading = false, projects, selectedProject, onSelectProject }: ProjectCostPanelProps) {
  const totals = projectTotals(sessions, buildRootLabels(projects));

  return (
    <Panel data-testid="project-cost-panel">
      <PanelTitle>
        By project
        <InfoDot title="Click a project to filter every panel to it - cost is per-project, not a share of the total" />
        {selectedProject && (
          <span className="filter-chip">
            Project: {selectedProject}
            <span className="clear" title="Clear filter" onClick={() => onSelectProject(undefined)}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </svg>
            </span>
          </span>
        )}
      </PanelTitle>
      <StackedBarPanel
        rows={toStackedBarRows(totals)}
        loading={loading}
        emptyText="No sessions yet."
        selectedKey={selectedProject}
        onSelectRow={(label) => onSelectProject(label === selectedProject ? undefined : label)}
        rowTestId={(row) => `project-row-${row.key}`}
      />
    </Panel>
  );
}
