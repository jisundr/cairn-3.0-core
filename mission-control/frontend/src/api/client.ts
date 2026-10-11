// Thin fetch wrapper over server.py's `/api/*` routes (TokenMeteringApp.
// handle_api - see server.py for the full route list). Every response is
// enveloped as { data, meta: { generated_at } }; `apiGet` unwraps `data`
// and throws on a non-2xx or a 404 (session/call not found).
import type {
  ApiError,
  CallDetail,
  CountRollupRow,
  DayDetail,
  Envelope,
  GroupRollupRow,
  ProjectsResponse,
  RangeKey,
  SessionSummary,
  SessionTrace,
  TaskCard,
  TaskDetail,
  TaskDocContent,
  Timeseries,
  UsageLimitEvent,
} from "./types";

export class ApiNotFoundError extends Error {}

async function apiGet<T>(path: string, params: Record<string, string | undefined> = {}): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, value);
  }
  const qs = query.toString();
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ""}`);
  if (res.status === 404) {
    const body = (await res.json()) as ApiError;
    throw new ApiNotFoundError(body.error);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({ error: res.statusText }))) as ApiError;
    throw new Error(body.error);
  }
  const body = (await res.json()) as Envelope<T>;
  return body.data;
}

export interface RangeParams {
  range: RangeKey;
  project?: string;
}

export const api = {
  projects: () => apiGet<ProjectsResponse>("/projects"),

  timeseries: ({ range, project }: RangeParams) => apiGet<Timeseries>("/rollup/timeseries", { range, project }),

  dayDetail: (date: string, project?: string) => apiGet<DayDetail>("/rollup/day-detail", { date, project }),

  sessions: ({ range, project }: RangeParams) => apiGet<SessionSummary[]>("/rollup/session", { range, project }),

  agentRollup: ({ range, project }: RangeParams) => apiGet<GroupRollupRow[]>("/rollup/agent", { range, project }),

  modelRollup: ({ range, project }: RangeParams) => apiGet<GroupRollupRow[]>("/rollup/model", { range, project }),

  toolRollup: ({ range, project }: RangeParams) => apiGet<CountRollupRow[]>("/rollup/tool", { range, project }),

  skillRollup: ({ range, project }: RangeParams) => apiGet<CountRollupRow[]>("/rollup/skill", { range, project }),

  mcpRollup: ({ range, project }: RangeParams) => apiGet<CountRollupRow[]>("/rollup/mcp-server", { range, project }),

  usageLimitEvents: ({ range, project }: RangeParams) =>
    apiGet<UsageLimitEvent[]>("/usage-limit-events", { range, project }),

  sessionTrace: (sessionId: string, project?: string) =>
    apiGet<SessionTrace>(`/session/${encodeURIComponent(sessionId)}/trace`, { project }),

  callDetail: (sessionId: string, n: number, project?: string) =>
    apiGet<CallDetail>(`/call/${encodeURIComponent(sessionId)}/${n}`, { project }),

  tasks: (project?: string) => apiGet<TaskCard[]>("/tasks", { project }),

  taskDetail: (project: string, folder: string) =>
    apiGet<TaskDetail>("/tasks/detail", { project, folder }),

  taskDoc: (project: string, folder: string, file: string) =>
    apiGet<TaskDocContent>("/tasks/doc", { project, folder, file }),
};
