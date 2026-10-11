import type { TaskCard } from "../api/types";

// PRD §6.9's attention signaling - title/favicon badge, chime, mute toggle -
// all client-computed from the same polled `/api/tasks` response, no new
// endpoint. This module holds the parts that need to survive App.tsx
// navigating between tabs: AppHeader (this module's only consumer) is
// unmounted and remounted on every tab switch (each page owns its own
// <AppHeader> instance, per App.tsx's own routing comment), so a per-
// component ref/state for "the previous poll's needs-attention set" or
// "has the chime been armed yet" would reset on every navigation and could
// misfire. Module-level state instead persists for the life of the page (a
// real reload resets it, matching PRD §6.9's "armed for the rest of that
// page session"), while surviving in-app tab changes.

export const BASE_TITLE = "~/ cairn/mission-control";

export function needsAttentionCount(tasks: TaskCard[] | undefined): number {
  return (tasks ?? []).filter((t) => t.needs_attention).length;
}

export function titleForCount(count: number): string {
  return count > 0 ? `(${count}) Mission Control` : BASE_TITLE;
}

// Short display label for a needs-attention card's badge (TaskCard.tsx) -
// `/api/tasks` gives the raw `key_info` string plus the boolean facts
// (transparency, not left for the frontend to re-derive per PRD §9), but
// not a canonical short label, so this matches the same trigger phrases
// PRD §6.2 names, in the same precedence order.
export function attentionLabel(keyInfo: string): string {
  if (/needs-human/.test(keyInfo)) return "needs-human";
  if (/stalled/.test(keyInfo)) return "stalled";
  return "needs attention";
}

function attentionKey(t: Pick<TaskCard, "project" | "folder">): string {
  return `${t.project}::${t.folder}`;
}

let previousAttentionKeys: Set<string> | null = null;
let chimeArmed = false;
let armListenerAttached = false;

// Diffs the current poll's Needs Attention folder set against the previous
// one - returns the keys newly present. The very first call each page
// session has no previous set to diff against, so it only seeds the
// baseline and returns nothing: a page load that already has existing
// Needs Attention cards must never itself chime.
export function newAttentionKeys(tasks: TaskCard[] | undefined): string[] {
  const current = new Set((tasks ?? []).filter((t) => t.needs_attention).map(attentionKey));
  const previous = previousAttentionKeys;
  previousAttentionKeys = current;
  if (previous === null) return [];
  const added: string[] = [];
  for (const key of current) {
    if (!previous.has(key)) added.push(key);
  }
  return added;
}

export function isChimeArmed(): boolean {
  return chimeArmed;
}

// Browser autoplay policy blocks unprompted audio until the user has
// interacted with the page at least once (PRD §6.9/§11) - arms on the first
// click anywhere in the app, once, for the rest of the page session. Safe
// to call from every AppHeader mount: guarded so only one listener is ever
// attached, and it's a no-op once already armed.
export function armChimeOnFirstInteraction(): void {
  if (chimeArmed || armListenerAttached) return;
  armListenerAttached = true;
  const onFirstClick = () => {
    chimeArmed = true;
    document.removeEventListener("click", onFirstClick);
  };
  document.addEventListener("click", onFirstClick);
}

const MUTE_STORAGE_KEY = "mc-attention-muted";

export function isMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setMuted(muted: boolean): void {
  try {
    if (muted) localStorage.setItem(MUTE_STORAGE_KEY, "1");
    else localStorage.removeItem(MUTE_STORAGE_KEY);
  } catch {
    // localStorage unavailable (private browsing, etc.) - the toggle just
    // won't persist across reloads; not worth failing the click over.
  }
}

const FAVICON_LINK_SELECTOR = 'link[rel="icon"]';

function getFaviconLink(): HTMLLinkElement {
  let link = document.querySelector<HTMLLinkElement>(FAVICON_LINK_SELECTOR);
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  return link;
}

// Canvas-drawn favicon (PRD §6.9). No icon file shipped with this app before
// this feature (`index.html` had no `<link rel="icon">` at all) - the
// "existing favicon" this composites a badge onto is itself drawn here: a
// plain dark square with the wordmark's own "mc" short-form. Needs
// Attention draws a small --remove dot in the corner on top of that same
// base drawing at runtime, not a second static image.
export function updateFavicon(hasAttention: boolean): void {
  const canvas = document.createElement("canvas");
  canvas.width = 32;
  canvas.height = 32;
  const ctx = canvas.getContext("2d");
  if (!ctx) return; // no canvas support (or a test environment) - leave as-is

  const accent = getComputedStyle(document.documentElement).getPropertyValue("--remove").trim() || "#b3372f";

  ctx.clearRect(0, 0, 32, 32);
  ctx.fillStyle = "#1e1e1e";
  ctx.fillRect(0, 0, 32, 32);
  ctx.fillStyle = "#fdfdfb";
  ctx.font = "700 15px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("mc", 16, 17);

  if (hasAttention) {
    ctx.beginPath();
    ctx.arc(25, 7, 6, 0, Math.PI * 2);
    ctx.fillStyle = accent;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#1e1e1e";
    ctx.stroke();
  }

  getFaviconLink().href = canvas.toDataURL("image/png");
}

// Test-only: this module's page-session-scoped state would otherwise leak
// across test cases sharing the same module instance.
export function _resetAttentionModuleStateForTests(): void {
  previousAttentionKeys = null;
  chimeArmed = false;
  armListenerAttached = false;
}
