import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TaskCard } from "../api/types";
import {
  _resetAttentionModuleStateForTests,
  armChimeOnFirstInteraction,
  attentionLabel,
  isChimeArmed,
  isMuted,
  needsAttentionCount,
  newAttentionKeys,
  setMuted,
  titleForCount,
  updateFavicon,
} from "./attention";

function task(overrides: Partial<TaskCard> = {}): TaskCard {
  return {
    project: "cairn-2.0",
    folder: "docs/tasks/2026-09-28-slug",
    parent: null,
    kind: "build",
    goal: "goal",
    key_info: "needs-human",
    last_log_date: "2026-09-28",
    last_log_time: "",
    column: "building",
    active: false,
    needs_attention: true,
    done: false,
    sub_tasks: null,
    ...overrides,
  };
}

beforeEach(() => {
  _resetAttentionModuleStateForTests();
  localStorage.clear();
});

describe("needsAttentionCount / titleForCount", () => {
  it("counts only needs_attention cards, whatever column they sit in and formats the title badge", () => {
    const tasks = [task({ folder: "a" }), task({ folder: "b", column: "planned", needs_attention: false }), task({ folder: "c" })];
    expect(needsAttentionCount(tasks)).toBe(2);
    expect(titleForCount(2)).toBe("(2) Mission Control");
  });

  it("reverts to the plain title at zero", () => {
    expect(needsAttentionCount([])).toBe(0);
    expect(titleForCount(0)).toBe("~/ cairn/mission-control");
  });
});

describe("attentionLabel", () => {
  it("matches each PRD §6.2 trigger phrase", () => {
    expect(attentionLabel("needs-human: pick a direction")).toBe("needs-human");
    expect(attentionLabel("stalled since last week")).toBe("stalled");
    expect(attentionLabel("awaiting plan approval")).toBe("needs attention");
    expect(attentionLabel("something else entirely")).toBe("needs attention");
  });
});

describe("newAttentionKeys", () => {
  it("never reports a new key on the first call (page load), even with existing entries", () => {
    const tasks = [task({ folder: "a" }), task({ folder: "b" })];
    expect(newAttentionKeys(tasks)).toEqual([]);
  });

  it("reports only the keys newly added since the previous call", () => {
    newAttentionKeys([task({ folder: "a" })]);
    const added = newAttentionKeys([task({ folder: "a" }), task({ folder: "b" })]);
    expect(added).toEqual(["cairn-2.0::b"]);
  });

  it("reports nothing when the Needs Attention set is unchanged between polls", () => {
    newAttentionKeys([task({ folder: "a" })]);
    expect(newAttentionKeys([task({ folder: "a" })])).toEqual([]);
  });

  it("does not report a folder that leaves Needs Attention and a different one that arrives as a repeat", () => {
    newAttentionKeys([task({ folder: "a" })]);
    const added = newAttentionKeys([task({ folder: "b" })]);
    expect(added).toEqual(["cairn-2.0::b"]);
  });
});

describe("chime arming", () => {
  it("starts unarmed and arms on the first click anywhere in the document", () => {
    expect(isChimeArmed()).toBe(false);
    armChimeOnFirstInteraction();
    expect(isChimeArmed()).toBe(false);
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(isChimeArmed()).toBe(true);
  });
});

describe("mute toggle", () => {
  it("defaults to unmuted and persists across the isMuted/setMuted pair", () => {
    expect(isMuted()).toBe(false);
    setMuted(true);
    expect(isMuted()).toBe(true);
    expect(localStorage.getItem("mc-attention-muted")).toBe("1");
    setMuted(false);
    expect(isMuted()).toBe(false);
    expect(localStorage.getItem("mc-attention-muted")).toBeNull();
  });
});

describe("updateFavicon", () => {
  // jsdom has no real canvas 2D context (HTMLCanvasElement.getContext
  // returns null without the optional `canvas` npm package) - stubbed here
  // at the browser-API boundary, same convention setupTests.ts already
  // uses for ResizeObserver/getBoundingClientRect.
  let arcCalls: number;
  let dataUrls: string[];

  beforeEach(() => {
    arcCalls = 0;
    dataUrls = [];
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      fillText: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(() => {
        arcCalls += 1;
      }),
      fill: vi.fn(),
      stroke: vi.fn(),
      set fillStyle(_v: string) {},
      set strokeStyle(_v: string) {},
      set lineWidth(_v: number) {},
      set font(_v: string) {},
      set textAlign(_v: string) {},
      set textBaseline(_v: string) {},
    } as unknown as CanvasRenderingContext2D);
    let n = 0;
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockImplementation(() => {
      const url = `data:image/png;base64,fake-${n++}`;
      dataUrls.push(url);
      return url;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.querySelectorAll('link[rel="icon"]').forEach((el) => el.remove());
  });

  it("creates the favicon link and only draws the badge dot when there's attention to show", () => {
    updateFavicon(false);
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    expect(link).not.toBeNull();
    expect(link?.href).toBe(dataUrls[0]);
    expect(arcCalls).toBe(0);

    updateFavicon(true);
    expect(arcCalls).toBe(1);
    expect(link?.href).toBe(dataUrls[1]);
  });
});
