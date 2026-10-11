import { useState } from "react";
import type { ProjectSummary } from "../api/types";
import { formatDateLabel } from "../lib/format";

interface InstallScopeRowProps {
  projects: ProjectSummary[];
  hostTag: string;
  selectedProject: string | undefined;
  onSelectProject: (project: string | undefined) => void;
  // Optional - only Overview has a selected-day concept (O2's click-to-
  // drill-into-a-day); Sessions List mounts this row without either prop,
  // so the chip simply never renders there.
  selectedDate?: string | null;
  onClearDate?: () => void;
}

// `.host-row` per the overview-revamp mockups - the app's hostname,
// previously rendered inside AppHeader's own `.host-tag` (F2 drops it from
// there), moves down onto its own row alongside install-type: a
// single-project install (`projects.length <= 1`) shows a read-only
// project-name chip (nothing to filter, already scoped to one project); a
// multi-project ("system") install shows an "All projects" dropdown that
// becomes a "Project: X ✕" chip once a project is picked - reusing
// ProjectCostPanel's own `.filter-chip`/`.clear` markup and click-to-clear
// interaction rather than a second implementation of it. Mounted on both
// Overview (wired to its own `projectFilter` state) and Sessions List
// (wired to its existing `projectFilter`/`setProjectFilter`, no new state).
// Overview also gets a second, independent "Date: X ✕" chip once O2's
// click-to-drill selects a day - same chip markup, own clear handler.
export function InstallScopeRow({
  projects,
  hostTag,
  selectedProject,
  onSelectProject,
  selectedDate,
  onClearDate,
}: InstallScopeRowProps) {
  const [open, setOpen] = useState(false);
  const multiProject = projects.length > 1;

  return (
    <div className="host-row">
      <div className="host-row-left">
        {!multiProject ? (
          <span className="filter-chip readonly" data-testid="install-scope-readonly">
            {projects[0]?.label ?? hostTag}
          </span>
        ) : selectedProject ? (
          <span className="filter-chip" data-testid="install-scope-chip">
            Project: {selectedProject}
            <span className="clear" title="Clear filter" onClick={() => onSelectProject(undefined)}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </svg>
            </span>
          </span>
        ) : (
          <div className="dropdown-wrap">
            <button
              type="button"
              className="dropdown-btn"
              data-testid="install-scope-dropdown"
              onClick={() => setOpen((o) => !o)}
            >
              All projects
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {open && (
              <div className="dropdown-menu" data-testid="install-scope-menu">
                {projects.map((p) => (
                  <div
                    key={p.label}
                    className="dropdown-item"
                    data-testid={`install-scope-option-${p.label}`}
                    onClick={() => {
                      onSelectProject(p.label);
                      setOpen(false);
                    }}
                  >
                    {p.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {selectedDate && onClearDate && (
          <span className="filter-chip" data-testid="install-scope-date-chip">
            Date: {formatDateLabel(selectedDate)}
            <span className="clear" title="Clear selected day" onClick={onClearDate}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </svg>
            </span>
          </span>
        )}
      </div>
      <div className="host-row-right">
        <span className="host-name mono" data-testid="install-scope-host">
          {hostTag}
        </span>
      </div>
    </div>
  );
}
