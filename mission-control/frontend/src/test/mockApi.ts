import { vi } from "vitest";

// Test-only fetch stand-in for `api/client.ts`'s `apiGet` - keyed by
// pathname (query params are handed to the handler, not matched against),
// so a test can vary its response by `range`/`project` without needing a
// real server. Mocks only the fetch boundary itself (a real external
// system as far as this codebase is concerned), never `client.ts` or
// `hooks.ts`.
type HandlerResult = { status?: number; body: unknown };
type Handler = (params: URLSearchParams) => HandlerResult;

export function installFetchMock(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: string | URL) => {
    const url = new URL(String(input), "http://localhost");
    const handler = handlers[url.pathname];
    if (!handler) {
      return new Response(JSON.stringify({ error: `unhandled path in test: ${url.pathname}` }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
    const { status = 200, body } = handler(url.searchParams);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function envelope<T>(data: T): HandlerResult {
  return { body: { data, meta: { generated_at: new Date().toISOString() } } };
}

export function ok<T>(data: T): HandlerResult {
  return envelope(data);
}

export function serverError(message = "request failed"): HandlerResult {
  return { status: 500, body: { error: message } };
}
