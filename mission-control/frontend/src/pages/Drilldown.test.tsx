import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CallDetail, SessionTrace } from "../api/types";
import { envelope, installFetchMock, serverError } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { Drilldown } from "./Drilldown";

const SESSION_ID = "a8de42aabbccddeeffgg1234c884";

const TRACE: SessionTrace = {
  session_id: SESSION_ID,
  started: "2026-09-25T11:58:00Z",
  ended: "2026-09-25T12:39:00Z",
  agents: [
    {
      agent: "builder",
      calls: 1,
      tokens: 184204,
      cost: 12.4,
      trace: [
        {
          position: 1,
          global_position: 1,
          request_id: "req-1",
          timestamp: "2026-09-25T11:58:00Z",
          model: "sonnet-5",
          input_tokens: 100,
          output_tokens: 200,
          cache_read_tokens: 0,
          cache_write_5m_tokens: 0,
          cache_write_1h_tokens: 0,
          cost: 12.4,
          duration_seconds: 1.2,
        },
      ],
    },
  ],
};

function callDetail(position: number): CallDetail {
  return {
    position,
    total: 1,
    session_id: SESSION_ID,
    project: "cairn-2.0",
    agent: "builder",
    request_id: `req-${position}`,
    timestamp: "2026-09-25T11:58:00Z",
    model: "sonnet-5",
    input_tokens: 100,
    output_tokens: 200,
    cache_read_tokens: 0,
    cache_write_5m_tokens: 0,
    cache_write_1h_tokens: 0,
    cost: 12.4,
    available: true,
    prompt: "I think we need to have backfill",
    response: "Confirmed: added automatic backfill.",
    tool_calls: [{ name: "Bash", summary: 'grep -n "backfill" parser.py' }],
  };
}

const noopTabChange = () => {};

function projectsHandlers() {
  return { "/api/projects": () => envelope({ hostname: "test-host", projects: [{ label: "cairn-2.0", parent: null }] }) };
}

describe("Drilldown", () => {
  it("renders the agent breakdown and transcript once the trace and call detail resolve", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(TRACE),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByTestId("agent-row-builder")).toHaveTextContent("$12.40");
    await waitFor(() => expect(screen.getByTestId("chat-thread")).toHaveTextContent("I think we need to have backfill"));
    expect(screen.getByText(/grep -n "backfill" parser.py/)).toBeInTheDocument();
  });

  it("shows the cairn version the session started under", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope({ ...TRACE, cairn_version: "0.40.0" }),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByTestId("drill-cairn-version")).toHaveTextContent("cairn 0.40.0");
  });

  it("shows cairn unknown when the session has no recorded version", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope({ ...TRACE, cairn_version: null }),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByTestId("drill-cairn-version")).toHaveTextContent("cairn unknown");
  });

  it("renders a version string as text, never as markup", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope({ ...TRACE, cairn_version: "<b>0.40.0</b>" }),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    const el = await screen.findByTestId("drill-cairn-version");
    expect(el).toHaveTextContent("cairn <b>0.40.0</b>");
    expect(el.querySelector("b")).toBeNull();
  });

  it("shows an unpriced agent cost with an info-dot", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () =>
        envelope({ ...TRACE, agents: [{ ...TRACE.agents[0], cost: null }] }),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByTestId("agent-row-builder")).toHaveTextContent("unknown");
    expect(screen.getAllByTitle("Model not yet priced").length).toBeGreaterThan(0);
  });

  it("shows a partial-failure banner with a working retry when a call detail fails, while the trace still renders", async () => {
    const fetchMock = installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(TRACE),
      [`/api/call/${SESSION_ID}/1`]: () => serverError("connection interrupted"),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByTestId("agent-row-builder")).toBeInTheDocument();
    expect(await screen.findByTestId("drilldown-partial-error-text")).toHaveTextContent("Couldn't load the last 1 call");

    const before = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByTestId("drilldown-partial-error-retry"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before));
  });

  it("navigates back via the drill-back link", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(TRACE),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });
    const onBack = vi.fn();
    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={onBack} />);

    fireEvent.click(await screen.findByText("← Overview"));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("wraps a turn's tool-calls in one toolcall-thread container, and omits it when a turn has none", async () => {
    const NO_CALLS_SESSION_ID = "no-tool-calls-session";
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(TRACE),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    const { container: withCalls } = renderWithClient(
      <Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />,
    );
    await waitFor(() => expect(screen.getByTestId("chat-thread")).toHaveTextContent("I think we need to have backfill"));

    const thread = withCalls.querySelector(".toolcall-thread");
    expect(thread).not.toBeNull();
    expect(thread!.querySelectorAll(".toolcall")).toHaveLength(1);

    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${NO_CALLS_SESSION_ID}/trace`]: () =>
        envelope({ ...TRACE, session_id: NO_CALLS_SESSION_ID }),
      [`/api/call/${NO_CALLS_SESSION_ID}/1`]: () => envelope({ ...callDetail(1), session_id: NO_CALLS_SESSION_ID, tool_calls: [] }),
    });

    const { container: withoutCalls } = renderWithClient(
      <Drilldown sessionId={NO_CALLS_SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />,
    );
    await waitFor(() => expect(screen.getByTestId("chat-thread")).toHaveTextContent("I think we need to have backfill"));
    expect(withoutCalls.querySelector(".toolcall-thread")).toBeNull();
  });

  it("labels each turn with its raw agentName, distinguishing the human's own turn from a subagent's", async () => {
    const MULTI_SESSION_ID = "multi-agent-session";
    const trace: SessionTrace = {
      session_id: MULTI_SESSION_ID,
      started: "2026-09-25T11:58:00Z",
      ended: "2026-09-25T12:39:00Z",
      agents: [
        {
          agent: "main",
          calls: 1,
          tokens: 100,
          cost: 1,
          trace: [
            {
              position: 1,
              global_position: 1,
              request_id: "req-main-1",
              timestamp: "2026-09-25T11:58:00Z",
              model: "sonnet-5",
              input_tokens: 10,
              output_tokens: 10,
              cache_read_tokens: 0,
              cache_write_5m_tokens: 0,
              cache_write_1h_tokens: 0,
              cost: 1,
              duration_seconds: 1,
            },
          ],
        },
        {
          agent: "cairn:builder",
          calls: 1,
          tokens: 100,
          cost: 1,
          trace: [
            {
              position: 2,
              global_position: 2,
              request_id: "req-builder-2",
              timestamp: "2026-09-25T11:59:00Z",
              model: "sonnet-5",
              input_tokens: 10,
              output_tokens: 10,
              cache_read_tokens: 0,
              cache_write_5m_tokens: 0,
              cache_write_1h_tokens: 0,
              cost: 1,
              duration_seconds: 1,
            },
          ],
        },
      ],
    };

    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${MULTI_SESSION_ID}/trace`]: () => envelope(trace),
      [`/api/call/${MULTI_SESSION_ID}/1`]: () => envelope({ ...callDetail(1), agent: "main", request_id: "req-main-1", prompt: "dispatch the builder" }),
      [`/api/call/${MULTI_SESSION_ID}/2`]: () => envelope({ ...callDetail(2), agent: "cairn:builder", request_id: "req-builder-2", prompt: "build the thing" }),
    });

    renderWithClient(<Drilldown sessionId={MULTI_SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    const humanOrigin = await screen.findByTestId(`turn-origin-${MULTI_SESSION_ID}-1`);
    expect(humanOrigin).toHaveTextContent("main");
    expect(humanOrigin).toHaveClass("turn-origin-human");

    const subagentOrigin = await screen.findByTestId(`turn-origin-${MULTI_SESSION_ID}-2`);
    expect(subagentOrigin).toHaveTextContent("cairn:builder");
    expect(subagentOrigin).toHaveClass("turn-origin-agent");
    expect(subagentOrigin).not.toHaveClass("turn-origin-human");
  });

  // F4: the shared AppHeader (wordmark, tabs, connection dot, refresh) now
  // renders above .drill-header - previously this page had no shared chrome
  // at all.
  it("F4: renders the shared AppHeader above the drill-header, tied to its own connection state", async () => {
    installFetchMock({
      ...projectsHandlers(),
      [`/api/session/${SESSION_ID}/trace`]: () => envelope(TRACE),
      [`/api/call/${SESSION_ID}/1`]: () => envelope(callDetail(1)),
    });

    renderWithClient(<Drilldown sessionId={SESSION_ID} activeTab="sessions" onTabChange={noopTabChange} onBack={() => {}} />);

    expect(await screen.findByRole("link", { name: "Sessions" })).toHaveClass("active");
    expect(screen.getByTitle("Connected to the local server")).toBeInTheDocument();
  });
});
