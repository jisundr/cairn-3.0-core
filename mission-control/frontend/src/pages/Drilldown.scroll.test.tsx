import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SessionTrace, TraceCall } from "../api/types";
import { envelope, installFetchMock } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { Drilldown } from "./Drilldown";

// Captures every options object Drilldown hands to `useVirtualizer`, while
// still delegating to the real implementation - this is a spy, not a fake:
// the merge-during-load bug lived entirely in how react-virtual's own
// measurement cache is keyed (by array index vs. by `getItemKey`), so
// asserting on the real library's input is the only way to pin the fix's
// actual contract rather than re-deriving it from Drilldown's own turn-
// building logic (which would just restate the implementation).
const capturedVirtualizerOptions: Array<{ count: number; getItemKey?: (index: number) => unknown }> = [];
vi.mock("@tanstack/react-virtual", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-virtual")>();
  return {
    ...actual,
    useVirtualizer: (options: Parameters<typeof actual.useVirtualizer>[0]) => {
      capturedVirtualizerOptions.push(options as unknown as { count: number; getItemKey?: (index: number) => unknown });
      return actual.useVirtualizer(options);
    },
  };
});

const SESSION_ID = "big-session";
const CALL_COUNT = 20;

function makeTrace(): SessionTrace {
  const trace: TraceCall[] = Array.from({ length: CALL_COUNT }, (_, i) => ({
    position: i + 1,
    global_position: i + 1,
    request_id: `req-${i + 1}`,
    timestamp: "2026-09-25T11:58:00Z",
    model: "sonnet-5",
    input_tokens: 10,
    output_tokens: 10,
    cache_read_tokens: 0,
    cache_write_5m_tokens: 0,
    cache_write_1h_tokens: 0,
    cost: 0.1,
    duration_seconds: 1,
  }));
  return {
    session_id: SESSION_ID,
    started: "2026-09-25T11:58:00Z",
    ended: "2026-09-25T12:39:00Z",
    agents: [{ agent: "builder", calls: CALL_COUNT, tokens: 200, cost: 2, trace }],
  };
}

// Goal 7: a large session's call details should load only for what's
// scrolled into view, not every call up front - the shape of the bug this
// covers (the transcript failing outright on a big session) only shows up
// with enough calls to exceed a viewport's worth.
describe("Drilldown - scroll-triggered call-detail loading", () => {
  it("fetches call detail only for calls scrolled into view, not the whole session up front", async () => {
    const fetchMock = installFetchMock({
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(makeTrace()),
      ...Object.fromEntries(
        Array.from({ length: CALL_COUNT }, (_, i) => [
          `/api/call/${SESSION_ID}/${i + 1}`,
          () =>
            envelope({
              position: i + 1,
              total: CALL_COUNT,
              session_id: SESSION_ID,
              project: "cairn-2.0",
              agent: "builder",
              request_id: `req-${i + 1}`,
              timestamp: "2026-09-25T11:58:00Z",
              model: "sonnet-5",
              input_tokens: 10,
              output_tokens: 10,
              cache_read_tokens: 0,
              cache_write_5m_tokens: 0,
              cache_write_1h_tokens: 0,
              cost: 0.1,
              available: true,
              prompt: `prompt ${i + 1}`,
              response: `response ${i + 1}`,
              tool_calls: [],
            }),
        ]),
      ),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={() => {}} onBack={() => {}} />);

    await waitFor(() => expect(screen.getByTestId("chat-thread")).toHaveTextContent(/prompt \d+/));

    const callDetailRequests = () =>
      fetchMock.mock.calls.filter((c) => String(c[0]).includes(`/api/call/${SESSION_ID}/`)).length;

    await waitFor(() => expect(callDetailRequests()).toBeGreaterThan(0));
    expect(callDetailRequests()).toBeLessThan(CALL_COUNT);

    fireEvent.scroll(screen.getByTestId("chat-thread"), { target: { scrollTop: 5000 } });

    await waitFor(() => expect(callDetailRequests()).toBeGreaterThan(0));
  });

  // Regression test for the overlapping-bubbles bug: `turns` (built fresh
  // every render by buildAgentTurns) reshuffles as call details resolve - a
  // call that renders as its own tiny "loading..." turn on one render can
  // become a non-first call absorbed into an earlier turn on the next, once
  // both calls' details have loaded and share a prompt. Without
  // `getItemKey`, react-virtual caches each item's measured size by its
  // array *index*, so the newly-shorter or newly-taller item at that index
  // inherits a stale sibling's size - the actual overlap mechanism. This
  // pins the fix's contract directly against the real library: `getItemKey`
  // must be wired, and a call's key must stop appearing anywhere once it's
  // absorbed into an earlier turn (not just linger at a new index).
  it("keys the virtualizer by each turn's own identity, not array position, across a merge", async () => {
    const MERGE_SESSION_ID = "merge-session";
    const trace: TraceCall[] = [1, 2, 3].map((position) => ({
      position,
      global_position: position,
      request_id: `req-${position}`,
      timestamp: "2026-09-25T11:58:00Z",
      model: "sonnet-5",
      input_tokens: 10,
      output_tokens: 10,
      cache_read_tokens: 0,
      cache_write_5m_tokens: 0,
      cache_write_1h_tokens: 0,
      cost: 0.1,
      duration_seconds: 1,
    }));
    const trimmedTrace: SessionTrace = {
      session_id: MERGE_SESSION_ID,
      started: "2026-09-25T11:58:00Z",
      ended: "2026-09-25T12:00:00Z",
      agents: [{ agent: "builder", calls: 3, tokens: 30, cost: 0.3, trace }],
    };

    function callDetailResponse(position: number, prompt: string) {
      return new Response(
        JSON.stringify(
          envelope({
            position,
            total: 3,
            session_id: MERGE_SESSION_ID,
            project: "cairn-2.0",
            agent: "builder",
            request_id: `req-${position}`,
            timestamp: "2026-09-25T11:58:00Z",
            model: "sonnet-5",
            input_tokens: 10,
            output_tokens: 10,
            cache_read_tokens: 0,
            cache_write_5m_tokens: 0,
            cache_write_1h_tokens: 0,
            cost: 0.1,
            available: true,
            prompt,
            response: `response ${position}`,
            tool_calls: [],
          }).body,
        ),
        { headers: { "Content-Type": "application/json" } },
      );
    }

    // Call 2 and 3 share a prompt (so they merge once *both* resolve); call
    // 3's detail resolves only when this test releases it - simulating the
    // exact ordering the bug depends on (call 3 briefly rendering as its own
    // top-level turn before the merge collapses it into call 2's turn).
    let releaseCall3!: () => void;
    const call3Gate = new Promise<void>((resolve) => {
      releaseCall3 = resolve;
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL) => {
        const pathname = new URL(String(input), "http://localhost").pathname;
        if (pathname === `/api/session/${MERGE_SESSION_ID}/trace`) {
          return new Response(JSON.stringify(envelope(trimmedTrace).body));
        }
        if (pathname === `/api/call/${MERGE_SESSION_ID}/1`) return callDetailResponse(1, "prompt A");
        if (pathname === `/api/call/${MERGE_SESSION_ID}/2`) return callDetailResponse(2, "prompt B");
        if (pathname === `/api/call/${MERGE_SESSION_ID}/3`) {
          await call3Gate;
          return callDetailResponse(3, "prompt B");
        }
        return new Response(JSON.stringify({ error: `unhandled path in test: ${pathname}` }), { status: 404 });
      }),
    );

    renderWithClient(<Drilldown sessionId={MERGE_SESSION_ID} activeTab="sessions" onTabChange={() => {}} onBack={() => {}} />);

    // Before call 3 resolves: three separate turns, one per call.
    await waitFor(() => expect(screen.getByTestId(`chat-turn-${MERGE_SESSION_ID}-3`)).toBeInTheDocument());
    expect(screen.getByTestId(`chat-turn-${MERGE_SESSION_ID}-1`)).toBeInTheDocument();
    expect(screen.getByTestId(`chat-turn-${MERGE_SESSION_ID}-2`)).toBeInTheDocument();

    const latestOptions = () => capturedVirtualizerOptions[capturedVirtualizerOptions.length - 1];
    expect(typeof latestOptions().getItemKey).toBe("function");
    const keysBeforeMerge = Array.from({ length: latestOptions().count }, (_, i) => latestOptions().getItemKey!(i));
    expect(keysBeforeMerge).toEqual(["builder-1", "builder-2", "builder-3"]);

    // Release call 3 - it now shares call 2's prompt, both loaded, so it
    // merges into call 2's turn and stops being its own top-level item.
    releaseCall3();

    await waitFor(() => expect(screen.queryByTestId(`chat-turn-${MERGE_SESSION_ID}-3`)).not.toBeInTheDocument());
    expect(screen.getByTestId(`chat-turn-${MERGE_SESSION_ID}-1`)).toBeInTheDocument();
    expect(screen.getByTestId(`chat-turn-${MERGE_SESSION_ID}-2`)).toBeInTheDocument();

    const keysAfterMerge = Array.from({ length: latestOptions().count }, (_, i) => latestOptions().getItemKey!(i));
    expect(keysAfterMerge).toEqual(["builder-1", "builder-2"]);
    // The bug's exact failure mode: "builder-3" dangling as a stale key some
    // index still resolves to, even though its turn no longer exists.
    expect(keysAfterMerge).not.toContain("builder-3");
  });
});
