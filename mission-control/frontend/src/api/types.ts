// Mirrors server.py's JSON shapes (TokenMeteringApp.handle_api). Every
// response is enveloped as { data, meta: { generated_at } }.

// "13w" is Overview's Calendar view's fixed 91-day window - never offered in
// RangeControl.tsx's own 6 options, only ContributionCalendar's internal
// useTimeseries call.
export type RangeKey = "today" | "7d" | "30d" | "month" | "6m" | "life" | "13w";

export interface Envelope<T> {
  data: T;
  meta: { generated_at: string };
}

export interface ProjectSummary {
  label: string;
  parent: string | null;
}

export interface ProjectsResponse {
  hostname: string;
  projects: ProjectSummary[];
}

export interface TimeseriesPoint {
  bucket: string;
  calls: number;
  tokens: number;
  cost: number | null;
  // On request, for the Trends stacked bar chart - same shape/sort
  // (descending tokens) DayDetail's own by_model already uses.
  by_model: ModelCostRow[];
}

export interface Timeseries {
  range: RangeKey;
  bucket: "hour" | "day";
  since: string;
  until: string;
  points: TimeseriesPoint[];
  total_tokens: number;
  total_cost: number | null;
}

export interface ModelCostRow {
  key: string;
  calls: number;
  tokens: number;
  cost: number | null;
}

export interface GroupRollupRow {
  key: string;
  calls: number;
  tokens: number;
  cost: number | null;
}

export interface CountRollupRow {
  key: string;
  count: number;
}

export interface DayDetail {
  date: string;
  total_tokens: number;
  total_cost: number | null;
  by_model: ModelCostRow[];
  // by_tool is call-count share only - tool_uses rows carry no cost of
  // their own and there's no join back to the cost-bearing calls row(s)
  // a tool invocation belongs to (see PLAN.md's By-tools note).
  by_tool: CountRollupRow[];
  by_agent: GroupRollupRow[];
}

export interface SessionSummary {
  session_id: string;
  project: string;
  started: string;
  ended: string;
  agents: string[];
  calls: number;
  tokens: number;
  cost: number | null;
  usage_limit_hit: boolean;
  label?: string;
  // The cairn version the session started under (server.py's
  // session_versions table); null when none was recorded.
  cairn_version?: string | null;
}

export interface UsageLimitEvent {
  id: number;
  session_id: string;
  timestamp: string;
  raw_entry: string;
  project: string;
}

export interface TraceCall {
  position: number;
  global_position: number;
  request_id: string;
  timestamp: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_5m_tokens: number;
  cache_write_1h_tokens: number;
  cost: number | "unknown";
  duration_seconds: number | null;
}

export interface AgentTrace {
  agent: string | null;
  calls: number;
  tokens: number;
  cost: number | null;
  trace: TraceCall[];
}

export interface SessionTrace {
  session_id: string;
  started: string;
  ended: string;
  agents: AgentTrace[];
  label?: string;
  cairn_version?: string | null;
}

export interface CallDetail {
  position: number;
  total: number;
  session_id: string;
  project: string;
  agent: string | null;
  request_id: string;
  timestamp: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_5m_tokens: number;
  cache_write_1h_tokens: number;
  cost: number | "unknown";
  available: boolean;
  prompt: string | null;
  response: string | null;
  tool_calls: { name: string; summary: string }[];
}

export interface ApiError {
  error: string;
  valid_ranges?: string[];
}

// Kanban board (v2, PRD §9) - one card per `docs/tasks/*/` folder (and its
// sub-task children), across every known project. `column` is the backend's
// own derived lifecycle stage (`parent_tasks` for a folder with sub-tasks
// until every child is done); `active`/`needs_attention` are orthogonal badge
// facts (any column), kept for transparency rather than re-derived here.
export type TaskColumn = "parent_tasks" | "scoping" | "awaiting_approval" | "planned" | "building" | "in_review" | "blocked" | "done";
export type TaskKind = "build" | "research" | "review";

export interface TaskSubTasksSummary {
  done: number;
  total: number;
}

export interface TaskCard {
  project: string;
  folder: string;
  parent: string | null;
  kind: TaskKind;
  goal: string;
  key_info: string;
  last_log_date: string;
  last_log_time: string;
  column: TaskColumn;
  active: boolean;
  needs_attention: boolean;
  done: boolean;
  // Present only on a folder that has sub-task children (PRD §6.4) - `null`
  // otherwise, never a `{done: 0, total: 0}` zero-value.
  sub_tasks: TaskSubTasksSummary | null;
}

// Detail drawer (v2, PRD §6.5/§9) - `GET /api/tasks/detail`. `activity` and
// `draft_content` are mutually exclusive: a `review` folder (DRAFT.md only)
// carries `draft_content`, everything else carries `activity`.
export interface TaskFrontmatter {
  goal?: string;
  paths?: string[];
  done_when?: string;
  out_of_scope?: string[];
  source?: string;
  path?: string;
  key_info?: string;
  flags?: string[];
}

export interface ActivityEntry {
  date: string;
  // The log line's HH:MM (UTC), or null when the line has no time.
  time: string | null;
  text: string;
}

export interface TaskSubTaskEntry {
  folder: string;
  column: TaskColumn;
  active: boolean;
  needs_attention: boolean;
  goal: string;
}

export interface TaskDoc {
  name: string;
  size: number;
  modified: string;
}

export interface TaskDetail {
  project: string;
  folder: string;
  parent: string | null;
  kind: TaskKind;
  column: TaskColumn;
  active: boolean;
  needs_attention: boolean;
  frontmatter: TaskFrontmatter;
  activity: ActivityEntry[] | null;
  draft_content: string | null;
  sub_tasks: TaskSubTaskEntry[] | null;
  docs: TaskDoc[];
}

export interface TaskDocContent {
  content: string;
}
