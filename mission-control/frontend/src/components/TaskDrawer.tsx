import { useMemo, useRef, useState } from "react";
import Markdown from "markdown-to-jsx";
import { useTaskDetail, useTaskDoc } from "../api/hooks";
import type { TaskColumn, TaskDetail, TaskDoc } from "../api/types";
import { attentionLabel } from "../lib/attention";
import { formatActivityStamp, taskDisplayName } from "../lib/format";

interface TaskDrawerProps {
  project: string;
  folder: string;
  tab: "details" | "docs";
  onClose: () => void;
  onTabChange: (tab: "details" | "docs") => void;
  // A sub-task row (Details tab, §6.5) re-opens the drawer on that child -
  // always the same project as the parent drawer already showing it.
  onOpenTask: (project: string, folder: string) => void;
}

// TaskDrawer.tsx per `board-drawer-open.html`/`board-drawer-docs.html`/
// `board-drawer-needs-attention.html` (PRD §6.5-§6.8, §10) - the app's first
// overlay: a centered modal (backdrop + dialog body, sized by `design.css`'s
// `.drawer` rule alone - a fluid width, no JS viewport check needed - same
// division of labor AppHeader's own F3 nav-collapse already established).
// Two tabs, both always mounted once data loads;
// `tab`/`onTabChange` and `onClose` are controlled by the caller (Kanban.tsx)
// so the open task/tab pair can live in the URL (§6.5's "URL state").
export function TaskDrawer({ project, folder, tab, onClose, onTabChange, onOpenTask }: TaskDrawerProps) {
  const detail = useTaskDetail(project, folder);
  const data = detail.data;

  return (
    <>
      <div className="drawer-backdrop" data-testid="drawer-backdrop" onClick={onClose} />
      <div className="drawer" data-testid="task-drawer">
        <div className="drawer-head">
          <div>
            <div className="drawer-title">{taskDisplayName(folder)}</div>
            {data && (
              <div className="drawer-badges">
                <span className="kcard-kind">{data.kind}</span>
                <ColumnBadge column={data.column} active={data.active} needsAttention={data.needs_attention} keyInfo={data.frontmatter.key_info} />
                {data.parent && (
                  <button
                    type="button"
                    className="drawer-parent-link"
                    data-testid="drawer-parent-link"
                    onClick={() => onOpenTask(data.project, data.parent!)}
                  >
                    {taskDisplayName(data.parent)}
                  </button>
                )}
                {data.sub_tasks && data.sub_tasks.length > 0 && (
                  <span className="drawer-subtask-count" data-testid="drawer-subtask-count">
                    {data.sub_tasks.length} sub-task{data.sub_tasks.length === 1 ? "" : "s"}
                  </span>
                )}
              </div>
            )}
          </div>
          <button type="button" className="drawer-close" aria-label="Close" onClick={onClose}>
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <line x1="6" y1="6" x2="18" y2="18" />
              <line x1="6" y1="18" x2="18" y2="6" />
            </svg>
          </button>
        </div>

        <div className="drawer-tabs">
          <button
            type="button"
            className={`drawer-tab${tab === "details" ? " active" : ""}`}
            data-testid="drawer-tab-details"
            onClick={() => onTabChange("details")}
          >
            Details
          </button>
          <button
            type="button"
            className={`drawer-tab${tab === "docs" ? " active" : ""}`}
            data-testid="drawer-tab-docs"
            onClick={() => onTabChange("docs")}
          >
            Docs{data ? ` (${data.docs.length})` : ""}
          </button>
        </div>

        {!data ? (
          <div className="drawer-body" data-testid="drawer-loading">
            {detail.isError ? "Couldn't load this task folder." : "Loading…"}
          </div>
        ) : tab === "details" ? (
          <div className="drawer-body">
            <DetailsTab data={data} onOpenTask={onOpenTask} />
          </div>
        ) : (
          <div className="drawer-body docs-tab">
            <DocsTab project={project} folder={folder} docs={data.docs} />
          </div>
        )}
      </div>
    </>
  );
}

const COLUMN_LABEL: Record<TaskColumn, string> = {
  parent_tasks: "Parent task",
  scoping: "Scoping",
  awaiting_approval: "Awaiting approval",
  planned: "Planned",
  building: "Building",
  in_review: "In review",
  blocked: "Blocked",
  done: "Done",
};

function ColumnBadge({
  column,
  active,
  needsAttention,
  keyInfo,
  variant = "default",
}: {
  column: TaskColumn;
  active: boolean;
  needsAttention: boolean;
  keyInfo?: string;
  variant?: "default" | "subtask";
}) {
  const modifier = variant === "subtask" ? " subtask-badge" : "";
  return (
    <>
      <span className={`kcard-kind${modifier}`}>{COLUMN_LABEL[column]}</span>
      {needsAttention && (
        <span className={`kcard-attn${modifier}`}>{keyInfo ? attentionLabel(keyInfo) : "needs attention"}</span>
      )}
      {active && (
        <span className={`kcard-ongoing${modifier}`}>
          <span className="status-dot" />
          active
        </span>
      )}
    </>
  );
}

// A paste-ready prompt for handing this task to a fresh session: a "resume"
// framing built around key_info (what's blocking/current state) for
// needs_attention, a "start" framing built around goal/done_when for planned -
// the two cases PromptComposer renders for. Wording/format are a
// build-time call (REQUIREMENTS.md Constraints); the fixed contract is just
// that it's non-empty whenever the relevant frontmatter fields exist and
// always names the project/folder so a fresh session knows where to look.
function buildPrompt(data: TaskDetail): string {
  const fm = data.frontmatter;
  const location = `Task: ${data.project} — ${data.folder}`;
  const doc = fm.path ? `Requirements doc: ${fm.path}` : null;

  if (data.needs_attention) {
    return [
      `Resume this task.`,
      location,
      doc,
      fm.goal ? `Goal: ${fm.goal}` : null,
      `What's blocking it: ${fm.key_info ?? "(no key_info recorded)"}`,
    ]
      .filter((line): line is string => line !== null)
      .join("\n");
  }

  return [
    `Start this task.`,
    location,
    doc,
    fm.goal ? `Goal: ${fm.goal}` : null,
    fm.done_when ? `Done when: ${fm.done_when}` : null,
  ]
    .filter((line): line is string => line !== null)
    .join("\n");
}

// Prompt composer (§6.8) - needs-attention (a "resume" framing) and planned (a
// "start" framing) cards, rendered above the frontmatter table. Uncontrolled
// textarea (a ref, not state): the "Copy" button just needs the field's
// current value at click time, and nothing else in this component (or
// anywhere else - §6.8's whole point) ever reads or sends it, so there's no
// reason to re-render on every keystroke; the generated prompt above is only
// the field's initial value, still fully editable.
function PromptComposer({ data }: { data: TaskDetail }) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [copied, setCopied] = useState(false);
  const isAttention = data.needs_attention;

  return (
    <div className={isAttention ? "reply-composer" : "reply-composer start"} data-testid="reply-composer">
      <div className="reply-head">
        <span className="reply-title">{isAttention ? "Needs your attention" : "Ready to start"}</span>
      </div>
      <div className="reply-reason">
        {isAttention
          ? `key_info: "${data.frontmatter.key_info ?? ""}"`
          : `goal: "${data.frontmatter.goal ?? ""}"`}
      </div>
      <textarea ref={textareaRef} className="reply-textarea" defaultValue={buildPrompt(data)} data-testid="reply-textarea" />
      <div className="reply-actions">
        <button
          type="button"
          className="reply-copy-btn"
          data-testid="reply-copy-btn"
          onClick={() => {
            void navigator.clipboard.writeText(textareaRef.current?.value ?? "");
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
        <span className="reply-note">
          Paste this into the terminal — mission control can&apos;t send it there directly.
        </span>
      </div>
    </div>
  );
}

// Details tab (§6.5): frontmatter as a field/value table, a parent's direct
// sub-task children (if any), then the activity timeline - or, for a
// `review` folder, `draft_content` in the timeline's place - all in one
// scroll, per the merged Details+Activity tab decision this folder's own
// STATE.md log records.
function DetailsTab({ data, onOpenTask }: { data: TaskDetail; onOpenTask: (project: string, folder: string) => void }) {
  const fm = data.frontmatter;
  const rows: { key: string; value: string; mono?: boolean }[] = [
    { key: "Folder", value: taskDisplayName(data.folder) },
    { key: "Project", value: data.project },
    { key: "Kind", value: data.kind },
    { key: "Column", value: COLUMN_LABEL[data.column] },
  ];
  if (fm.goal) rows.push({ key: "Goal", value: fm.goal });
  if (fm.paths?.length) rows.push({ key: "Paths", value: fm.paths.join(", "), mono: true });
  if (fm.done_when) rows.push({ key: "Done when", value: fm.done_when });
  if (fm.out_of_scope?.length) rows.push({ key: "Out of scope", value: fm.out_of_scope.join(", ") });
  if (fm.source) rows.push({ key: "Source", value: fm.source });
  if (fm.path) rows.push({ key: "Path", value: fm.path, mono: true });
  if (fm.key_info) rows.push({ key: "Key info", value: fm.key_info });
  if (fm.flags?.length) rows.push({ key: "Flags", value: fm.flags.join(", ") });

  return (
    <>
      {(data.needs_attention || data.column === "planned") && <PromptComposer data={data} />}

      <div className="drawer-section">
        <div className="drawer-section-title">Details</div>
        <table className="detail">
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="dt-key">{row.key}</td>
                <td className={row.mono ? "dt-val mono" : "dt-val"}>{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.sub_tasks && data.sub_tasks.length > 0 && (
        <div className="drawer-section">
          <div className="drawer-section-title">Sub-tasks</div>
          <div className="subtask-list">
            {data.sub_tasks.map((st) => (
              <button
                key={st.folder}
                type="button"
                className="subtask-row"
                data-testid={`subtask-row-${st.folder}`}
                onClick={() => onOpenTask(data.project, st.folder)}
              >
                <span className="subtask-name">{taskDisplayName(st.folder)}</span>
                <span className="subtask-goal">{st.goal}</span>
                <ColumnBadge column={st.column} active={st.active} needsAttention={st.needs_attention} variant="subtask" />
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="drawer-section">
        <div className="drawer-section-title">{data.activity !== null ? "Activity" : "Draft"}</div>
        {data.activity === null ? (
          <div className="timeline-text" style={{ whiteSpace: "pre-wrap" }}>
            {data.draft_content}
          </div>
        ) : data.activity.length === 0 ? (
          <div className="timeline-empty" data-testid="timeline-empty">
            No activity yet.
          </div>
        ) : (
          <div className="timeline">
            {data.activity.map((entry, i) => (
              <div className="timeline-item" key={`${entry.date}-${i}`}>
                <div className="timeline-date" title={entry.time ? `${entry.date} ${entry.time} UTC` : undefined}>
                  {formatActivityStamp(entry.date, entry.time)}
                </div>
                <div className="timeline-text">{entry.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function formatDocSize(bytes: number): string {
  return bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`;
}

// A doc image's `src` as the browser should fetch it: a scheme URL
// (`https:`, `data:`, ...) or a protocol-relative `//host` one is left as-is;
// anything else - `./x.png`, `mockups/y.webp`, and also `/abs.png` or
// `../x.png` - goes through `/api/tasks/asset`, so the server's containment
// guard stays the single place that decides what a task folder may serve.
export function taskAssetUrl(project: string, folder: string, src: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(src) || src.startsWith("//")) return src;
  let path = src;
  try {
    path = decodeURIComponent(src);
  } catch {
    path = src;
  }
  return `/api/tasks/asset?${new URLSearchParams({ project, folder, path })}`;
}

// markdown-to-jsx's `img` override for the Docs tab: routes relative srcs
// through `taskAssetUrl` and falls back to the alt text when the image is
// refused, missing, or has no usable src (the default sanitizer drops a
// `javascript:` one).
function TaskDocImage({
  project,
  folder,
  src,
  alt,
  title,
}: {
  project: string;
  folder: string;
  src?: string | null;
  alt?: string;
  title?: string;
}) {
  // Keyed on the src that failed, so a new src gets a fresh attempt.
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (!src || failedSrc === src) {
    return (
      <span className="doc-img-missing" data-testid="doc-img-missing">
        {alt || src || "image"}
      </span>
    );
  }
  return (
    <img
      src={taskAssetUrl(project, folder, src)}
      alt={alt}
      title={title}
      loading="lazy"
      onError={() => setFailedSrc(src)}
    />
  );
}

const DOC_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

// Docs tab (§6.6): a persistent left sidebar + main content pane, GitLab's
// own file-browser layout - both the sidebar and the <=900px
// `.docs-mobile-picker` dropdown (reusing InstallScopeRow.tsx's own
// dropdown-wrap/-btn/-menu markup verbatim, not a second dropdown) are
// always rendered; `design.css`'s existing 900px breakpoint alone decides
// which one shows, the same CSS-only division of labor AppHeader's F3
// nav-collapse already established (no matchMedia/innerWidth check here).
function DocsTab({ project, folder, docs }: { project: string; folder: string; docs: TaskDoc[] }) {
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const doc = useTaskDoc(project, folder, selectedDoc);
  const markdownOptions = useMemo(
    () => ({
      disableParsingRawHTML: true,
      overrides: { img: { component: TaskDocImage, props: { project, folder } } },
    }),
    [project, folder],
  );

  if (docs.length === 0) {
    return (
      <div className="docs-main-empty" data-testid="docs-empty" style={{ width: "100%" }}>
        no other documents
      </div>
    );
  }

  const selectedMeta = docs.find((d) => d.name === selectedDoc) ?? null;

  return (
    <div className="docs-layout">
      <div className="docs-sidebar">
        <div className="docs-sidebar-path">
          <b>{project}</b> / {taskDisplayName(folder)}
        </div>
        <div className="docs-file-list">
          {docs.map((d) => (
            <button
              key={d.name}
              type="button"
              className={`docs-file${selectedDoc === d.name ? " active" : ""}`}
              data-testid={`docs-file-${d.name}`}
              onClick={() => setSelectedDoc(d.name)}
            >
              <span className="doc-icon">{DOC_ICON}</span>
              <span className="doc-name">{d.name}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="docs-mobile-picker">
        <div className="dropdown-wrap">
          <button
            type="button"
            className="dropdown-btn"
            data-testid="docs-mobile-dropdown"
            onClick={() => setMobileOpen((o) => !o)}
          >
            {selectedDoc ?? "Select a document"}
            <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          {mobileOpen && (
            <div className="dropdown-menu" data-testid="docs-mobile-menu">
              {docs.map((d) => (
                <div
                  key={d.name}
                  className="dropdown-item"
                  data-testid={`docs-mobile-option-${d.name}`}
                  onClick={() => {
                    setSelectedDoc(d.name);
                    setMobileOpen(false);
                  }}
                >
                  {d.name}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="docs-main">
        {selectedDoc === null ? (
          <div className="docs-main-empty" data-testid="docs-select-placeholder">
            select a document
          </div>
        ) : doc.data ? (
          <>
            <div className="docs-main-head">
              <div className="docs-main-title">{selectedDoc}</div>
              {selectedMeta && (
                <div className="docs-main-meta">
                  {formatDocSize(selectedMeta.size)} · modified {selectedMeta.modified}
                </div>
              )}
            </div>
            <div className="doc-render">
              <Markdown options={markdownOptions}>{doc.data.content}</Markdown>
            </div>
          </>
        ) : (
          <div className="docs-main-empty" data-testid="docs-loading">
            {doc.isError ? "Couldn't load this document." : "Loading…"}
          </div>
        )}
      </div>
    </div>
  );
}
