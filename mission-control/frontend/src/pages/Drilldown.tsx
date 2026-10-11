import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";
import { useCallDetails, useProjects, useSessionTrace } from "../api/hooks";
import type { AgentTrace, CallDetail, TraceCall } from "../api/types";
import { AppHeader, type AppTab } from "../components/AppHeader";
import { InfoDot, isUnknownCost } from "../components/InfoDot";
import { Panel, PanelTitle } from "../components/Panel";
import { PanelError } from "../components/PanelError";
import { StackedBarPanel, type StackedBarRow } from "../components/StackedBarPanel";
import { formatCairnVersion, formatCost, formatDateLabel, formatSessionDuration, formatTokens, shortId } from "../lib/format";

interface DrilldownProps {
  sessionId: string;
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onBack: () => void;
}

interface MergedCall {
  call: TraceCall;
  agentName: string;
}

interface CallEntry extends MergedCall {
  detail: CallDetail | undefined;
  isLoading: boolean;
  isError: boolean;
}

interface Turn {
  key: string;
  agentName: string;
  firstGlobalPosition: number;
  calls: CallEntry[];
}

// Groups one agent's own chronological calls into turns: consecutive calls
// merge into the same turn only when both the current and immediately
// preceding call's detail have loaded (without error), are both available,
// and the current call's prompt is non-empty and string-equals the
// previous one's - a same-agent walk-back-to-the-same-prompt tool round
// trip. Ported unchanged from token-metering/frontend's SessionDrilldown.
// tsx (per the build plan's instruction to keep this merge logic, only
// reskin the markup around it) - just extended with `isError` so a
// failed call-detail fetch starts a new turn rather than silently merging.
function buildAgentTurns(
  agentName: string,
  trace: TraceCall[],
  detailByPosition: Map<number, { detail: CallDetail | undefined; isLoading: boolean; isError: boolean }>,
): Turn[] {
  const turns: Turn[] = [];
  let previous: CallEntry | null = null;

  for (const call of trace) {
    const found = detailByPosition.get(call.global_position);
    const entry: CallEntry = {
      call,
      agentName,
      detail: found?.detail,
      isLoading: found?.isLoading ?? false,
      isError: found?.isError ?? false,
    };

    const canMerge =
      previous !== null &&
      !previous.isLoading &&
      !entry.isLoading &&
      !previous.isError &&
      !entry.isError &&
      previous.detail?.available === true &&
      entry.detail?.available === true &&
      !!entry.detail.prompt &&
      entry.detail.prompt === previous.detail.prompt;

    if (canMerge) {
      turns[turns.length - 1].calls.push(entry);
    } else {
      turns.push({ key: `${agentName}-${call.global_position}`, agentName, firstGlobalPosition: call.global_position, calls: [entry] });
    }

    previous = entry;
  }

  return turns;
}

// pages/Drilldown.tsx per drilldown-loaded.html/drilldown-error.html -
// markup reskinned, turn-merge/virtualization logic ported unchanged (see
// buildAgentTurns above). Unlike token-metering/frontend's
// SessionDrilldown.tsx, neither mockup nor (Drilldown-specific) DESIGN.md
// content defines a click-to-dim agent-selection interaction or a per-call
// metadata line in the transcript, so this reskin doesn't carry either
// forward - the transcript here renders only each turn's prompt bubble,
// its tool-call lines, and its final response bubble, matching the
// mockups' literal markup.
export function Drilldown({ sessionId, activeTab, onTabChange, onBack }: DrilldownProps) {
  const projects = useProjects();
  const { data: trace, refetch: refetchTrace } = useSessionTrace(sessionId);
  const scrollRef = useRef<HTMLDivElement>(null);

  const totalTokens = trace ? trace.agents.reduce((sum, a) => sum + a.tokens, 0) : 0;
  const totalCost = trace
    ? trace.agents.some((a) => a.cost === null)
      ? ("unknown" as const)
      : trace.agents.reduce((sum, a) => sum + (a.cost ?? 0), 0)
    : null;

  const mergedCalls: MergedCall[] = (trace?.agents ?? [])
    .flatMap((agent) => agent.trace.map((call) => ({ call, agentName: agent.agent ?? "unknown" })))
    .sort((a, b) => a.call.global_position - b.call.global_position);

  // Goal 7: call details load for what's actually scrolled into view, not
  // every call in the session up front - a large session otherwise fires
  // one request per call at mount, which can exceed what the browser/server
  // sustain and fail outright. `visiblePositions` only grows (a position
  // once fetched stays in `useCallDetails`' argument, so react-query's own
  // per-position `queryKey` cache - not a refetch - serves it if it scrolls
  // out of view and back). Reset per session: a stale position set from the
  // previous session would otherwise carry over, since Drilldown doesn't
  // remount between sessions (App.tsx never keys it by sessionId).
  const [visiblePositions, setVisiblePositions] = useState<Set<number>>(new Set());
  useEffect(() => {
    setVisiblePositions(new Set());
  }, [sessionId]);

  const detailQueries = useCallDetails(sessionId, [...visiblePositions]);
  const detailByQueryPosition = new Map(
    [...visiblePositions].map((position, i) => [
      position,
      { detail: detailQueries[i]?.data, isLoading: detailQueries[i]?.isLoading ?? false, isError: detailQueries[i]?.isError ?? false },
    ]),
  );

  const detailByPosition = new Map<number, { detail: CallDetail | undefined; isLoading: boolean; isError: boolean }>();
  mergedCalls.forEach((m) => {
    detailByPosition.set(
      m.call.global_position,
      detailByQueryPosition.get(m.call.global_position) ?? { detail: undefined, isLoading: false, isError: false },
    );
  });

  const failedCount = detailQueries.filter((q) => q.isError).length;

  const turns: Turn[] = (trace?.agents ?? [])
    .flatMap((agent) => buildAgentTurns(agent.agent ?? "unknown", agent.trace, detailByPosition))
    .sort((a, b) => a.firstGlobalPosition - b.firstGlobalPosition);

  // `turns` is recomputed fresh on every render (see the comment above), and
  // its merge logic (buildAgentTurns) means the same array index can hold a
  // tiny single-call "loading..." placeholder turn on one render and a much
  // taller, fully-merged turn on the next, as call details stream in during
  // scroll. Without `getItemKey`, react-virtual v3 caches each item's
  // measured size by array index, so a resize like that gets misapplied to
  // whatever now sits at that index - the previous turn's cached height
  // stays attached to the new, differently-sized turn - producing the
  // overlapping-bubbles bug this was keyed by index. `turn.key` is a stable,
  // content-derived id (`${agentName}-${call.global_position}`, the first
  // call in the turn), so it stays attached to the same underlying turn
  // across renders regardless of which index it lives at; a call that gets
  // absorbed into an earlier turn as a non-first call simply stops appearing
  // as its own top-level key, which react-virtual handles the same as any
  // other item leaving the list (it drops the stale cache entry, it doesn't
  // require an append-only key set).
  const rowVirtualizer = useVirtualizer({
    count: turns.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 120,
    overscan: 5,
    getItemKey: (index) => turns[index]?.key ?? index,
  });

  const virtualItems = rowVirtualizer.getVirtualItems();
  useEffect(() => {
    const positions = new Set<number>();
    for (const item of virtualItems) {
      const turn = turns[item.index];
      if (!turn) continue;
      for (const entry of turn.calls) positions.add(entry.call.global_position);
    }
    setVisiblePositions((prev) => {
      let changed = false;
      const next = new Set(prev);
      for (const position of positions) {
        if (!next.has(position)) {
          next.add(position);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    // `turns` is recomputed every render (not memoized), so this effect uses
    // its own shallow scan of `virtualItems`/`turns` rather than relying on
    // React's dependency-array identity check to decide when to run - it
    // runs every render, but the `changed` guard above means `setState` (and
    // therefore a re-render) only actually happens when a genuinely new
    // position enters view.
  });

  if (!trace) return null;

  function handleRefresh() {
    refetchTrace();
    detailQueries.forEach((q) => q.refetch());
  }

  return (
    <div className="shell">
      <AppHeader activeTab={activeTab} onTabChange={onTabChange} connected={!projects.isError} onRefresh={handleRefresh} />

      <div className="drill-header">
        <div className="drill-left">
          <a
            className="drill-back"
            href="/sessions"
            onClick={(e) => {
              e.preventDefault();
              onBack();
            }}
          >
            ← Overview
          </a>
          <div className="drill-title">Session {trace.label || shortId(trace.session_id)}</div>
          <div className="drill-meta">
            {formatDateLabel(trace.started.slice(0, 10))} · {formatSessionDuration(trace.started, trace.ended)} runtime ·{" "}
            <span data-testid="drill-cairn-version">{formatCairnVersion(trace.cairn_version)}</span>
          </div>
        </div>
        <div className="drill-right">
          <div className="drill-tokens">{totalTokens.toLocaleString()} tokens</div>
          <div className="drill-cost mono">
            {formatCost(totalCost)}
            {isUnknownCost(totalCost) && <InfoDot />}
          </div>
        </div>
      </div>

      {failedCount > 0 && (
        <div className="panel err" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, padding: "12px 18px" }}>
          <PanelError
            message={`Couldn't load the last ${failedCount} call${failedCount === 1 ? "" : "s"} — connection interrupted`}
            onRetry={() => detailQueries.forEach((q) => q.isError && q.refetch())}
            testId="drilldown-partial-error"
          />
        </div>
      )}

      <div className="drill-grid">
        <Panel>
          <PanelTitle>Agents in this session</PanelTitle>
          <StackedBarPanel
            data-testid="agents-in-session"
            rows={agentRows(trace.agents)}
            rowTestId={(r) => `agent-row-${r.key}`}
            emptyText="No agents in this session."
          />
        </Panel>

        <Panel>
          <PanelTitle>Transcript</PanelTitle>
          <div className="transcript" ref={scrollRef} data-testid="chat-thread">
            <div style={{ height: rowVirtualizer.getTotalSize(), width: "100%", position: "relative" }}>
              {rowVirtualizer.getVirtualItems().map((virtualItem) => {
                const turn = turns[virtualItem.index];
                return (
                  <div
                    key={turn.key}
                    data-index={virtualItem.index}
                    ref={rowVirtualizer.measureElement}
                    style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${virtualItem.start}px)` }}
                  >
                    <ChatTurn sessionId={sessionId} turn={turn} />
                  </div>
                );
              })}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

// Feeds Drilldown's "Agents in this session" panel into StackedBarPanel,
// matching Overview's By-models/By-agents panels (which moved from HbarList
// to StackedBarPanel during the dashboard revamp) rather than the row-capped
// HbarList this panel used before - same shape as Overview.tsx's
// costTokenRows helper.
function agentRows(agents: AgentTrace[]): StackedBarRow[] {
  return agents.map((agent) => ({
    key: agent.agent ?? "unknown",
    value: agent.tokens,
    display: `${formatCost(agent.cost)} (${formatTokens(agent.tokens)})`,
    unknown: isUnknownCost(agent.cost),
  }));
}

function ChatTurn({ sessionId, turn }: { sessionId: string; turn: Turn }) {
  const failed = turn.calls.some((c) => c.isError);
  if (failed) {
    return (
      <div className="placeholder-block" data-testid={`chat-turn-${sessionId}-${turn.firstGlobalPosition}`}>
        next turn's tool calls — failed to load, see banner above
      </div>
    );
  }

  const firstCall = turn.calls[0];
  const lastCall = turn.calls[turn.calls.length - 1];
  const finalResponse = lastCall.detail && lastCall.detail.available ? (lastCall.detail.response ?? "") : "";
  // A call whose position hasn't entered `visiblePositions` yet (freshly
  // scrolled into the virtualizer's overscan window, one render before the
  // scroll-triggered fetch effect above requests it) has no query result at
  // all - `detail` undefined and `isLoading` false, the same shape as
  // "still loading" from this component's point of view, so both read the
  // same "loading…" rather than one of them going momentarily blank.
  const promptText = firstCall.detail
    ? firstCall.detail.available
      ? firstCall.detail.prompt ?? ""
      : "Transcript unavailable."
    : "loading…";
  const hasToolCalls = turn.calls.some((entry) => (entry.detail?.available ? entry.detail.tool_calls.length > 0 : false));

  return (
    <div className="chat-turn" data-testid={`chat-turn-${sessionId}-${turn.firstGlobalPosition}`}>
      <div
        className={`turn-origin ${turn.agentName === "main" ? "turn-origin-human" : "turn-origin-agent"}`}
        data-testid={`turn-origin-${sessionId}-${turn.firstGlobalPosition}`}
      >
        {turn.agentName}
      </div>
      <div className="bubble prompt">{promptText}</div>
      {hasToolCalls && (
        <div className="toolcall-thread">
          {turn.calls.map((entry) =>
            (entry.detail?.available ? entry.detail.tool_calls : []).map((toolCall, i) => (
              <div className="toolcall" key={`${entry.call.request_id}-${i}`}>
                <span className="dot" />
                <b>{toolCall.name}</b> — {toolCall.summary}
              </div>
            )),
          )}
        </div>
      )}
      {finalResponse && <div className="bubble response">{finalResponse}</div>}
    </div>
  );
}
