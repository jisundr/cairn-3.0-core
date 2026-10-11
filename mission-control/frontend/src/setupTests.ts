import "@testing-library/jest-dom/vitest";

// vitest's jsdom integration only forwards window properties it finds via
// `Object.getOwnPropertyNames(window)` - jsdom defines `localStorage`/
// `sessionStorage` as getters on its Window *prototype*, not as the window
// instance's own properties, so they're silently missed; what shows through
// instead is Node's own built-in `localStorage` global (Node 22+), which
// warns and stays unusable without a `--localstorage-file` flag. The
// attention-signaling mute toggle (PRD §6.9, `lib/attention.ts`) is this
// app's first use of `localStorage` at all - a minimal in-memory stand-in
// closes that gap for tests without touching the real browser behavior
// this app actually runs under.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear() {
    this.store.clear();
  }
  getItem(key: string) {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }
  key(index: number) {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.store.delete(key);
  }
  setItem(key: string, value: string) {
    this.store.set(key, String(value));
  }
}

function installLocalStorageShimIfNeeded() {
  try {
    if (typeof globalThis.localStorage !== "undefined" && globalThis.localStorage !== null) {
      globalThis.localStorage.setItem("__mc_probe__", "1");
      globalThis.localStorage.removeItem("__mc_probe__");
      return;
    }
  } catch {
    // Falls through to install the shim below.
  }
  Object.defineProperty(globalThis, "localStorage", {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  });
}
installLocalStorageShimIfNeeded();

// jsdom has no layout engine (every element reports 0 size) and no
// ResizeObserver at all - @tanstack/react-virtual (the Drilldown page's
// virtualized transcript) needs both to compute a non-empty visible
// range. Without these, every virtualized test would see an empty
// scroll container regardless of how much data it was given.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 800 });
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, value: 800 });

// Recharts' <ResponsiveContainer> (goals 3-6) measures its container via
// `getBoundingClientRect()` on mount, not `offsetWidth`/`offsetHeight` -
// jsdom has no layout engine, so that always reports an all-zero rect,
// which Recharts then refuses to render into (a zero-size chart is treated
// as "wait for a resize event that never comes" under the ResizeObserver
// stub above). Same fixed non-zero size as the offset* stubs, so every
// chart gets a stable, non-zero area to lay out into under test.
Element.prototype.getBoundingClientRect = () =>
  ({ x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 800, width: 800, height: 800, toJSON() {} }) as DOMRect;

// jsdom has no real media playback engine - HTMLMediaElement.play() throws
// "Not implemented" by default. The attention chime (PRD §6.9, AppHeader)
// plays a bundled asset through a plain `HTMLAudioElement`; tests need
// `.play()` to resolve instead of throwing so they can assert it was
// called, not exercise real audio decoding.
if (typeof HTMLMediaElement !== "undefined") {
  HTMLMediaElement.prototype.play = () => Promise.resolve();
  HTMLMediaElement.prototype.pause = () => {};
}

// jsdom has no real canvas 2D context (HTMLCanvasElement.getContext returns
// null and logs "Not implemented" without the optional `canvas` npm
// package). The favicon badge (PRD §6.9, `lib/attention.ts`) already
// no-ops on a null context, so this is cosmetic stderr noise in every test
// that mounts `AppHeader`, not a real failure - a global no-op stub silences
// it; `attention.test.ts` overrides this per-suite via `vi.spyOn` where it
// actually asserts on canvas calls.
if (typeof HTMLCanvasElement !== "undefined") {
  const noopCtx = {
    clearRect() {},
    fillRect() {},
    fillText() {},
    beginPath() {},
    arc() {},
    fill() {},
    stroke() {},
    set fillStyle(_v: string) {},
    set strokeStyle(_v: string) {},
    set lineWidth(_v: number) {},
    set font(_v: string) {},
    set textAlign(_v: string) {},
    set textBaseline(_v: string) {},
  } as unknown as CanvasRenderingContext2D;
  HTMLCanvasElement.prototype.getContext = (() => noopCtx) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";
}
