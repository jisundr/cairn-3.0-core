import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionSummary } from "../api/types";
import { envelope, installFetchMock, serverError } from "../test/mockApi";
import { renderWithClient } from "../test/renderWithClient";
import { SessionsList } from "./SessionsList";

const noop = () => {};

const SESSION: SessionSummary = {
  session_id: "a8de42aabbccddeeffgg1234c884",
  project: "cairn-2.0",
  started: "2026-09-25T11:58:00Z",
  ended: "2026-09-25T12:39:00Z",
  agents: ["builder"],
  calls: 12,
  tokens: 184204,
  cost: 12.4,
  usage_limit_hit: false,
};

// S1: a second, older, cheaper, shorter-duration, lower-token session -
// distinguishes every sortable column from SESSION so a sort test can tell
// which row landed first without relying on the default order alone.
const OLDER_SESSION: SessionSummary = {
  session_id: "older-session-0000000000000000",
  project: "cairn-2.0",
  started: "2026-09-20T09:00:00Z",
  ended: "2026-09-20T09:05:00Z",
  agents: ["builder"],
  calls: 2,
  tokens: 500,
  cost: 1.0,
  usage_limit_hit: false,
};

function install(overrides: Record<string, ReturnType<typeof envelope> | { status: number; body: unknown }> = {}) {
  return installFetchMock({
    "/api/projects": () =>
      overrides["/api/projects"] ?? envelope({ hostname: "test-host", projects: [{ label: "cairn-2.0", parent: null }] }),
    "/api/rollup/session": () => overrides["/api/rollup/session"] ?? envelope([SESSION]),
  });
}

describe("SessionsList", () => {
  // A `?range=`/`?sort=`/etc. query param set by an earlier test in this
  // file would otherwise leak into the next one's initial read.
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("renders the sessions table and navigates to a drilldown on row click", async () => {
    install();
    const onSelectSession = vi.fn();
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={onSelectSession} />);

    await waitFor(() => expect(screen.getByTestId("sessions-table")).toHaveTextContent("$12.40"));
    // S2: single-project install - the redundant Project column is dropped.
    expect(screen.getByTestId("sessions-table")).not.toHaveTextContent("cairn-2.0");

    fireEvent.click(screen.getByText("a8de42…c884"));
    expect(onSelectSession).toHaveBeenCalledWith(SESSION.session_id);
  });

  it("shows each session's cairn version, marking only those below the newest in the range as older", async () => {
    install({
      "/api/rollup/session": envelope([
        { ...SESSION, session_id: "sess-newest", cairn_version: "0.40.0" },
        { ...SESSION, session_id: "sess-older", cairn_version: "0.9.3" },
        { ...SESSION, session_id: "sess-unknown", cairn_version: null },
        { ...SESSION, session_id: "sess-absent" },
      ]),
    });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getByTestId("cairn-version-sess-newest")).toHaveTextContent("0.40.0"));
    expect(screen.getByTestId("cairn-version-sess-older")).toHaveTextContent("0.9.3");
    expect(screen.getByTestId("cairn-older-sess-older")).toHaveAttribute("title", "Older than 0.40.0, newest in this range");
    // A no-break space, not just CSS margin: assistive tech reads "0.9.3 older",
    // and the badge cannot wrap away from its version in a narrow cell.
    expect(screen.getByTestId("cairn-version-sess-older").textContent).toBe("0.9.3\u00a0older");
    expect(screen.getByTestId("cairn-version-sess-newest").textContent).toBe("0.40.0");
    expect(screen.queryByTestId("cairn-older-sess-newest")).toBeNull();
    expect(screen.getByTestId("cairn-version-sess-unknown")).toHaveTextContent("unknown");
    expect(screen.queryByTestId("cairn-older-sess-unknown")).toBeNull();
    expect(screen.getByTestId("cairn-version-sess-absent")).toHaveTextContent("unknown");
    expect(screen.queryByTestId("cairn-older-sess-absent")).toBeNull();
  });

  it("measures older against the newest version across the whole range, not just the current page", async () => {
    const sessions: SessionSummary[] = Array.from({ length: 30 }, (_, i) => ({
      ...SESSION,
      session_id: `session-${i}`,
      started: new Date(Date.UTC(2026, 8, 25 - i)).toISOString(),
      ended: new Date(Date.UTC(2026, 8, 25 - i, 0, 30)).toISOString(),
      cairn_version: i === 29 ? "0.41.0" : "0.40.0",
    }));
    install({ "/api/rollup/session": envelope(sessions) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getAllByTestId(/^session-row-/)).toHaveLength(25));
    expect(screen.getByTestId("cairn-older-session-0")).toBeInTheDocument();
    expect(screen.getAllByTestId(/^cairn-older-/)).toHaveLength(25);
    expect(screen.getByTestId("pagination-count")).toHaveTextContent("Showing 1–25 of 30");
  });

  it("marks nothing older when every session shares one version", async () => {
    install({
      "/api/rollup/session": envelope([
        { ...SESSION, cairn_version: "0.40.0" },
        { ...OLDER_SESSION, cairn_version: "0.40.0" },
      ]),
    });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getAllByTestId(/^session-row-/)).toHaveLength(2));
    expect(screen.queryAllByTestId(/^cairn-older-/)).toHaveLength(0);
  });

  // S2: pagination.
  it("S2: paginates at 25 rows, Prev disabled on page 1, Next advances the page", async () => {
    const sessions: SessionSummary[] = Array.from({ length: 30 }, (_, i) => ({
      ...SESSION,
      session_id: `session-${i}`,
      started: new Date(Date.UTC(2026, 8, 25 - i)).toISOString(),
      ended: new Date(Date.UTC(2026, 8, 25 - i, 0, 30)).toISOString(),
    }));
    install({ "/api/rollup/session": envelope(sessions) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getAllByTestId(/^session-row-/)).toHaveLength(25));
    expect(screen.getByTestId("pagination-count")).toHaveTextContent("Showing 1–25 of 30");
    expect(screen.getByTestId("pagination-prev")).toBeDisabled();

    fireEvent.click(screen.getByTestId("pagination-next"));
    expect(screen.getAllByTestId(/^session-row-/)).toHaveLength(5);
    expect(screen.getByTestId("pagination-count")).toHaveTextContent("Showing 26–30 of 30");
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("S2: shows the Project column only on a multi-project (system) install", async () => {
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "cairn-2.0", parent: null },
            { label: "wardstone", parent: null },
          ],
        }),
      "/api/rollup/session": () => envelope([SESSION]),
    });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getByTestId("sessions-table")).toHaveTextContent("cairn-2.0"));
  });

  it("shows PanelError with a working retry when the sessions fetch fails", async () => {
    const fetchMock = install({ "/api/rollup/session": serverError() });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    expect(await screen.findByTestId("sessions-error-text")).toHaveTextContent("Couldn't load sessions — request failed");
    const before = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByTestId("sessions-error-retry"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before));
  });

  it("shows the empty state when no sessions fall in the selected range", async () => {
    install({ "/api/rollup/session": envelope([]) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    expect(await screen.findByTestId("sessions-empty")).toHaveTextContent("No sessions in this range");
  });

  // S1: sort controls.
  function rowOrder(): string[] {
    return screen.getAllByTestId(/^session-row-/).map((r) => r.getAttribute("data-testid")!);
  }

  it("S1: defaults to Started, descending - newest session first", async () => {
    install({ "/api/rollup/session": envelope([OLDER_SESSION, SESSION]) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    expect(rowOrder()).toEqual([`session-row-${SESSION.session_id}`, `session-row-${OLDER_SESSION.session_id}`]);
  });

  it("S1: the direction toggle reverses the current column's order", async () => {
    install({ "/api/rollup/session": envelope([SESSION, OLDER_SESSION]) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    fireEvent.click(screen.getByTestId("sort-direction"));

    expect(rowOrder()).toEqual([`session-row-${OLDER_SESSION.session_id}`, `session-row-${SESSION.session_id}`]);
  });

  // Regression for the dropdown-clip fix: `.sort-group`'s `overflow: hidden`
  // used to clip `.dropdown-menu` out of view even though the toggle logic
  // itself worked - assert the menu actually mounts/unmounts, not just the
  // sort order it produces.
  it("S1: clicking the sort control shows the dropdown menu, and picking an option closes it", async () => {
    install({ "/api/rollup/session": envelope([SESSION, OLDER_SESSION]) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    expect(screen.queryByTestId("sort-menu")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("sort-select"));
    expect(screen.getByTestId("sort-menu")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("sort-option-cost"));
    expect(screen.queryByTestId("sort-menu")).not.toBeInTheDocument();
  });

  it("S1: a column-header click sorts by that column, same as picking it from the dropdown", async () => {
    install({ "/api/rollup/session": envelope([SESSION, OLDER_SESSION]) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    // Tokens, descending (the default direction) - SESSION (184204) first.
    fireEvent.click(screen.getByTestId("sort-header-tokens"));
    expect(rowOrder()).toEqual([`session-row-${SESSION.session_id}`, `session-row-${OLDER_SESSION.session_id}`]);

    // The dropdown's own "Cost" option sets the same state - OLDER_SESSION
    // ($1.00) sorts last under descending, unchanged from the toggle above.
    fireEvent.click(screen.getByTestId("sort-select"));
    fireEvent.click(screen.getByTestId("sort-option-cost"));
    expect(rowOrder()).toEqual([`session-row-${SESSION.session_id}`, `session-row-${OLDER_SESSION.session_id}`]);
  });

  // URL state: range/project/sort/dir/page all round-trip through query
  // params, mirroring Overview.tsx's own view/project/date convention.
  it("loads with ?range=30d&project=wardstone&sort=cost&dir=asc in the URL and restores all four", async () => {
    window.history.pushState(null, "", "/?range=30d&project=wardstone&sort=cost&dir=asc");
    let capturedRange: string | null = null;
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "cairn-2.0", parent: null },
            { label: "wardstone", parent: null },
          ],
        }),
      "/api/rollup/session": (params) => {
        capturedRange = params.get("range");
        return envelope([SESSION, OLDER_SESSION]);
      },
    });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    expect(capturedRange).toBe("30d");
    expect(screen.getByTestId("range-seg-30d").className).toContain("active");
    expect(screen.getByTestId("install-scope-chip")).toHaveTextContent("Project: wardstone");
    // Cost ascending - OLDER_SESSION ($1.00) sorts before SESSION ($12.40).
    expect(rowOrder()).toEqual([`session-row-${OLDER_SESSION.session_id}`, `session-row-${SESSION.session_id}`]);
  });

  it("loads with ?page=2 and restores that page, without a stray Prev/Next click", async () => {
    const sessions: SessionSummary[] = Array.from({ length: 30 }, (_, i) => ({
      ...SESSION,
      session_id: `session-${i}`,
      started: new Date(Date.UTC(2026, 8, 25 - i)).toISOString(),
      ended: new Date(Date.UTC(2026, 8, 25 - i, 0, 30)).toISOString(),
    }));
    window.history.pushState(null, "", "/?page=2");
    install({ "/api/rollup/session": envelope(sessions) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getByTestId("pagination-count")).toHaveTextContent("Showing 26–30 of 30"));
    expect(screen.getByTestId("pagination-next")).toBeDisabled();
  });

  it("changing the sort direction updates the URL's dir param without clobbering range/project", async () => {
    window.history.pushState(null, "", "/?range=30d&project=wardstone");
    installFetchMock({
      "/api/projects": () =>
        envelope({
          hostname: "test-host",
          projects: [
            { label: "cairn-2.0", parent: null },
            { label: "wardstone", parent: null },
          ],
        }),
      "/api/rollup/session": () => envelope([SESSION, OLDER_SESSION]),
    });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(rowOrder()).toHaveLength(2));
    expect(new URLSearchParams(window.location.search).get("dir")).toBe("desc");

    fireEvent.click(screen.getByTestId("sort-direction"));

    await waitFor(() => expect(new URLSearchParams(window.location.search).get("dir")).toBe("asc"));
    const params = new URLSearchParams(window.location.search);
    expect(params.get("range")).toBe("30d");
    expect(params.get("project")).toBe("wardstone");
  });

  it("changing the range resets the page URL param to 1", async () => {
    const sessions: SessionSummary[] = Array.from({ length: 30 }, (_, i) => ({
      ...SESSION,
      session_id: `session-${i}`,
      started: new Date(Date.UTC(2026, 8, 25 - i)).toISOString(),
      ended: new Date(Date.UTC(2026, 8, 25 - i, 0, 30)).toISOString(),
    }));
    window.history.pushState(null, "", "/?page=2");
    install({ "/api/rollup/session": envelope(sessions) });
    renderWithClient(<SessionsList activeTab="sessions" onTabChange={noop} onSelectSession={noop} />);

    await waitFor(() => expect(screen.getByTestId("pagination-count")).toHaveTextContent("Showing 26–30 of 30"));

    fireEvent.click(screen.getByTestId("range-seg-life"));

    await waitFor(() => expect(new URLSearchParams(window.location.search).get("page")).toBe("1"));
    expect(new URLSearchParams(window.location.search).get("range")).toBe("life");
  });
});
