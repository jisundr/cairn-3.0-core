import { attentionLabel } from "../lib/attention";
import { formatLastTouched, taskDisplayName } from "../lib/format";
import type { TaskCard as TaskCardData } from "../api/types";

interface TaskCardProps {
  task: TaskCardData;
  // Dropped on a single-project install the same way SessionsList's own
  // Project column is (S2) - every card already belongs to the one known
  // project, so the tag would be redundant noise on every card.
  showProject: boolean;
  // Opens the detail drawer (../04-frontend-drawer-docs/'s own build) on
  // this card's own folder - optional so a caller with no drawer yet (there
  // is none left in this app) can still render a plain, non-interactive
  // card, matching this component's pre-drawer behavior exactly. Carries
  // this card's own already-known `project` (never re-derived by the
  // caller from a folder-string-only lookup, which breaks when two
  // projects happen to produce a same-named folder).
  onClick?: (project: string, folder: string) => void;
}

// `.kcard` per `board-single-project.html`/`board-multi-project.html` -
// renders one task-folder card: goal, kind, the sub-task `parent`-reference
// indicator (§6.3), and a parent's own `sub_tasks` "N of M done" bar (§6.4).
// The parent indicator is a plain, non-interactive span rather than the
// mockup's `<a href="#">` - it names what §6.3 calls "the link back to the
// parent", but the drawer it would open (§6.5) is `../04-frontend-drawer-
// docs/`'s own build, not yet real - a clickable link to nowhere would be
// worse than an honest, static label for now.
export function TaskCard({ task, showProject, onClick }: TaskCardProps) {
  const subTasks = task.sub_tasks;
  const progressPct = subTasks && subTasks.total > 0 ? Math.round((subTasks.done / subTasks.total) * 100) : 0;

  return (
    <div
      className="kcard"
      data-testid={`task-card-${task.folder}`}
      onClick={onClick ? () => onClick(task.project, task.folder) : undefined}
      style={onClick ? { cursor: "pointer" } : undefined}
    >
      <div className="kcard-top">
        <span className="kcard-kind">{task.kind}</span>
        {showProject && <span className="kcard-project">{task.project}</span>}
      </div>
      {task.parent && (
        <span className="kcard-parent" data-testid="kcard-parent">
          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2.5" strokeLinecap="round">
            <path d="M9 6l6 6-6 6" />
          </svg>
          {taskDisplayName(task.parent)}
        </span>
      )}
      <div className="kcard-title">{taskDisplayName(task.folder)}</div>
      <div className="kcard-goal">{task.goal}</div>
      {subTasks && (
        <div className="kcard-progress">
          <div className="hbar-track" style={{ width: 42, height: 5 }}>
            <div className="hbar-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="kcard-progress-label">
            {subTasks.done} of {subTasks.total} done
          </span>
        </div>
      )}
      <div className="kcard-foot">
        <span className="kcard-date">last touched {formatLastTouched(task.last_log_date, task.last_log_time)}</span>
        {task.needs_attention && <span className="kcard-attn">{attentionLabel(task.key_info)}</span>}
        {task.active && (
          <span className="kcard-ongoing">
            <span className="status-dot" />
            active
          </span>
        )}
      </div>
    </div>
  );
}
