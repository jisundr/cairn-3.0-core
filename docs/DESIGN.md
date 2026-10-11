---
name: cairn — Mission Control
description: A local usage dashboard read the way you read a git diff — exact values, color only where something changed or broke.
colors:
  bg: "#fdfdfb"
  panel: "#ffffff"
  panel-sunken: "#f7f7f3"
  ink: "#1e1e1e"
  ink-soft: "#5b5b52"
  ink-faint: "#75756b"
  border: "#dcdcd3"
  border-soft: "#ece9e1"
  add: "#2f8f49"
  add-bg: "#eaf6ec"
  add-line: "#3fae5c"
  remove: "#b3372f"
  remove-bg: "#fbebe9"
  remove-line: "#d33f3f"
typography:
  wordmark:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "16px"
    fontWeight: 700
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "10px–11px"
    letterSpacing: "0.04em"
    textTransform: "uppercase"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "10px–25px"
    fontWeight: "400–700"
    fontFeature: "tabular-nums, ligatures disabled"
rounded:
  xs: "2px"
  sm: "4px"
  md: "5px"
  lg: "6px"
  xl: "7px"
  2xl: "8px"
  full: "50%"
spacing:
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "14px"
  xl: "16px"
  2xl: "18px"
  3xl: "20px"
components:
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.2xl}"
    padding: "16px 18px"
  stat-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.2xl}"
    padding: "14px 16px"
  seg-active:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "5px 12px"
  icon-btn:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.lg}"
    width: "28px"
    height: "28px"
  filter-chip:
    backgroundColor: "{colors.add-bg}"
    textColor: "{colors.add}"
    rounded: "12px"
    padding: "3px 6px 3px 10px"
  btn-block:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "8px"
---

# Design System: cairn — Mission Control

## Overview

**Creative North Star: "The Diff You Verify"**

Mission control reads live usage the same way cairn reads its own install: as a diff you check, not a chart you admire. This is cairn's own Lockfile world (`docs/marketing/DESIGN-landing.md`) carried from a static marketing page into a live-data Operate surface — same near-white/near-black editor ground, same JetBrains Mono, same diff-green/diff-red semantic pair — landed against a dashboard's actual furniture (stat cards, range tabs, bar charts, heatmap, ranked lists) instead of a hero diff panel. It replaces token-metering's outgoing "Clean Minimal SaaS" instrument-panel system (Public Sans + Martian Mono, indigo accent) in this file; that system's own record is superseded, not merged — see `docs/PRODUCT.md` and the landing design record for why the two worlds were kept apart until this build deliberately closed the gap.

The build deliberately refuses the gradient-tile, soft-shadow "AI analytics dashboard" default — the same default token-metering's predecessor had already circled and rejected once, now refused a second time in a different idiom. There is no dedicated accent color chosen for decoration: the diff's own add/remove pair does the accenting work color would otherwise do, so "in use" or "selected" reads as diff-green the same way an added line would, and nothing on the page is colored just to be colored.

As of this build, only the Overview/Loaded screen is implemented in high fidelity, in both a light and a dark theme (both real CSS, both screenshotted and reviewed — not a light build with an untested dark stub). The other nine wireframed states (Overview Error/Empty, Sessions List, Session Drilldown, First Launch) exist only as structural wireframes in the sibling `wireframes/` directory; this record describes the system this one screen actually established, for the next pass to extend rather than reinvent.

**Key Characteristics:**
- Near-white ground (`--bg` `#fdfdfb`) / near-black ink (`--ink` `#1e1e1e`) in light mode, with a full dark counterpart (`--bg` `#14140f`, `--ink` `#ecece2`) reusing the same semantic roles rather than inventing new ones
- No separate decorative accent: diff-green (`--add`) marks connected/selected/added/up, diff-red (`--remove`) is reserved for disconnected/error/removed — color signals state change, not brand
- Every measured value (cost, tokens, counts, durations, timestamps, percentages) renders in JetBrains Mono with tabular numerals and ligatures disabled; every label and every sentence of prose renders in the system sans
- Flat, hairline-bordered surfaces throughout — no `box-shadow` anywhere in the shipped screen
- A signature diff-gutter device, `.hbar-sign`, gives each row in a filterable ranked list a `+`/blank sign column, so selecting a row reads like a line landing in a diff rather than a row highlighting
- The wordmark is text-only mono (`~/ cairn/mission-control`) — no icon, no glyph, no logomark

## Colors

The same editor/diff palette as the Lockfile world, unchanged in hue and role: a near-white/near-black neutral pair carries structure and prose; diff-green and diff-red are the only two saturated colors, and both are reserved for state, never decoration.

### Primary
- **Diff Green** (`--add` `#2f8f49` light / `#5fd67f` dark, wash `--add-bg` `#eaf6ec` / `#17301f`, line accent `--add-line` `#3fae5c` / `#5fd67f`): marks connected (status dot, `title="Connected to the local server"`), active (the app-tab underline, the active range-segment isn't green but the `add-line` is reserved for its own uses below), selected (a selected `hbar-row`'s background wash and `hbar-fill`), and added (a filter chip's `+`, its one-shot flash animation, the `hbar-sign.add` gutter mark on the row that drove the filter). Also the global focus-ring color and the `::selection` highlight.
- **Diff Red** (`--remove` `#b3372f` light / `#ef7268` dark, wash `--remove-bg`, line accent `--remove-line`): reserved for disconnected/error/removed semantics. Not yet exercised by this screen's happy-path state (no active error/disconnect in Overview/Loaded), but declared in `:root` alongside green as the pair's other half — the next pass's Overview/Error screen draws from this token rather than inventing a new one.

### Neutral
- **Ground** (`--bg` `#fdfdfb` / `#14140f`): the page background.
- **Panel** (`--panel` `#ffffff` / `#1a1a14`): every stat card, panel, and the active range-segment's own fill.
- **Panel Sunken** (`--panel-sunken` `#f7f7f3` / `#1f1f18`): hover fill for icon buttons and clickable `hbar-row`s — the one recessed tone in the system, used only on interaction, never at rest.
- **Ink** (`--ink` `#1e1e1e` / `#ecece2`): primary text, stat values, active-tab text, hbar labels.
- **Ink Soft** (`--ink-soft` `#5b5b52` / `#a7a79a`): secondary text — inactive tab labels, hbar-fill's at-rest fill color, icon-button default color.
- **Ink Faint** (`--ink-faint` `#75756b` / `#8a8a7e`): tertiary text — range/stat/panel labels, host-tag, "updated Ns ago" caption, hbar scope annotations (`· local`, `· project`), bar-chart day labels, the info-dot's tooltip trigger, the default (unfilled) `hbar-sign` blank column.
- **Border** (`--border` `#dcdcd3` / `#35352b`) / **Border Soft** (`--border-soft` `#ece9e1` / `#2a2a21`): the two hairline weights. Border carries panel/card/icon-button edges; border-soft carries the segmented-tab track, hbar-row dividers, the default bar/track/heatmap-cell fill.

### Named Rules
**The Diff-Semantics Rule (carried forward).** Green means connected/added/selected/up; red means disconnected/error/removed/down. Neither color is available for decoration, chart variety, or generic emphasis — this build introduces no third color and no per-series hue set, unlike the outgoing system's channel-color set (`--ch1`–`--ch4`). A ranked list with several rows (by tool, by agent, by model) stays on the ink/gray scale at rest; green appears only on the row that is actually selected or filtered.

**The No-Decoration-Accent Rule.** This world has no accent color chosen for brand or decoration the way the outgoing system reserved indigo for "active/selected" as a UI-color convention. Every colored pixel in this build is a diff-semantic claim (something connected, added, or selected) rather than a UI-chrome convention borrowed from a generic dashboard kit.

## Typography

**Body/Label Font:** system sans stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`)
**Mono Font:** JetBrains Mono (400/500/600/700, with `ui-monospace, SFMono-Regular, Menlo, monospace` fallback)

**Character:** the same Sans/Mono split as the Lockfile world, re-applied to a data surface: sans carries every label and every word of prose; mono carries every measured value and the wordmark itself. There is no third display face — the wordmark is simply mono at its largest size in this screen (16px).

### Hierarchy
- **Wordmark** (700 weight, 16px, mono, `-0.01em` tracking): `~/ cairn/mission-control`, dimmed/bright segments distinguishing the `~/ ` prefix, the app name, and the `/mission-control` sub-segment. Text-only — no icon or glyph accompanies it.
- **Body** (400 weight, 14px, 1.5 line-height, sans): the page's base font-size; not otherwise a distinct visible role in this screen (Overview/Loaded has no running prose block).
- **Label** (500–600 weight, 10px–11px, mono, `0.04em` tracking, uppercase): range label, stat-card labels, panel titles, host-tag, app-tab text — carried in mono here, a deliberate divergence from the landing page's Label role (which stays sans); this build's labels read as terminal/diff chrome, not prose micro-copy.
- **Mono/Readout** (400–700 weight, 10px–25px, tabular-nums, ligatures disabled): stat-card headline values (25px), hbar values, bar-day labels, updated-at caption, host-tag — every number or path-like string that needs to be trusted or compared exactly.

### Named Rules
**The Sans/Mono Split Rule (carried forward, with one divergence).** Mono carries every measured value and the wordmark; sans carries running prose. Unlike the landing page's split, this build's uppercase micro-labels (range/stat/panel titles) also render in mono rather than sans — recorded here as this screen's own established convention, since a dashboard's labels ("COST TODAY", "SESSIONS (7D)") read closer to terminal/status chrome than to page copy.

**The No-Ligatures Rule (carried forward).** Every mono context disables contextual alternates and ligatures (`font-variant-ligatures: none; font-feature-settings: "calt" 0, "liga" 0`) — load-bearing here for the same reason as the landing page: numeric and path-like content must render verbatim, never re-drawn as a glyph.

## Layout

A single centered column, `.shell` capped at `max-width: 1320px` with `20px 28px 48px` padding. A slim header (wordmark + app tabs at left; hostname, status dot, refresh button, updated-at caption at right) sits above a bottom border, `20px` margin below it.

Below the header: a range-selection row (mono uppercase "Range" label + a segmented pill group of six tabs: Today/7D/30D/Month/6M/Life), then a flat wrapping row of stat cards (`flex: 1 1 180px`, `gap: 14px`), then the two-column panel grid (`grid-template-columns: 1.3fr 1fr`, `gap: 16px`) that collapses to one column under `900px`. The left column stacks the day/cost chart, activity heatmap, and by-tool panel; the right column stacks per-project cost, by-agent, and by-model panels.

At `900px`: the grid collapses to one column, shell padding tightens to `16px 16px 36px`, and the header's right-hand cluster (hostname/status/refresh/updated-at) wraps to full width, space-between.

## Elevation & Depth

Flat. No `box-shadow` appears anywhere in the shipped screen. Depth is a two-step surface stack — page (`--bg`) vs. card/panel (`--panel`) — plus a 1px `--border`, with `--panel-sunken` as a third tone reserved for hover states (icon buttons, clickable hbar rows) rather than at-rest layering.

### Named Rules
**The Border-Only Depth Rule (carried forward).** Every stat card, panel, and control is flat at rest, separated from its ground by a single 1px border, never a shadow. This build introduces no exception (the landing page's one blur exception, the sticky header's `backdrop-filter`, is not present on this screen).

## Shapes

Corners run small: `2px` on bars and heatmap cells, `4px`–`5px` on inputs/segments/hbar tracks, `6px`–`7px` on icon buttons and segment tracks, `8px` on stat cards and panels. A true circle is reserved for the status dot and the filter chip's clear button. Borders are a single hairline weight (`1px` `--border` or `--border-soft`) throughout — no dashed borders, no border-weight state changes; selected/active state is conveyed by a background/text-color swap, never a heavier border.

## Components

### Header & Navigation
Mono wordmark at 16px/700, its three segments (`~/ ` prefix dimmed, `cairn` at full ink, `/mission-control` sub-segment in `--ink-soft`) reading as one path rather than a logo-plus-name pair. App-level tabs (Overview/Sessions) are plain text links with a 2px bottom border that appears only on the active tab, colored `--add-line` — the tab convention is an underline, not a filled pill. The right-hand cluster is hostname (mono, faint) → status dot (`--add`, titled "Connected to the local server") → icon-only refresh button → "updated Ns ago" caption (mono, faint).

### Range Segments
A `--border-soft`-tracked pill group (`border-radius: 7px`, `2px` padding) of six mono, uppercase-free labels (Today/7D/30D/Month/6M/Life); the active segment gets a `--panel` background, `--border` border, and `--ink` (600-weight) text — the same "background+text swap, never a solid fill" idiom the outgoing system used for its tabs, now re-expressed in the diff palette.

### Stat Cards
A `--panel` card (`8px` radius, `14px 16px` padding) holding a mono uppercase 11px `--ink-faint` label above a 25px/600 mono `--ink` value. A stat whose value is unresolvable (e.g. "Cost (7D)" when a model isn't yet priced) renders `unknown*` at a smaller 20px in `--ink-faint` rather than a zero, paired with an inline info-dot icon whose `title` explains why.

### Panels
A `--panel` card (`8px` radius, `16px 18px` padding) with a mono uppercase 11px `--ink-faint` panel-title row (`justify-content: space-between`, so a title can carry trailing chrome like a filter chip). Holds a bar chart, heatmap, or hbar list.

### Bar Chart (Tokens/cost per day)
Flex-column bars (`max-width: 30px`, `2px 2px 0 0` radius) on a `--border-soft` fill; the current day's bar is distinguished by an `--ink-soft` fill rather than the diff-green (green is reserved for connection/selection state, not "today"). Day labels render below each bar in 10px mono `--ink-faint`.

### Activity Heatmap
A 24-column grid of `aspect-ratio: 1` cells (`2px` radius), each cell either the `--border-soft` empty fill or a `color-mix` of `--add` at 15%/45%/100% opacity over that same base — a single-hue intensity ramp on the diff-green channel, not a separate multi-hue scale.

### Ranked List / `.hbar-row` (signature component)
A row of: an `.hbar-sign` gutter column (1ch wide, mono, `--ink-faint` blank by default, `--add` when marked `+`) — a literal diff-gutter device borrowed from the Lockfile world's diff-line gutters, now driving list selection instead of line numbers — a fixed-width mono label (with an optional faint `hbar-scope` annotation, e.g. `· local`, `· project`), a flex-fill `hbar-track` (7px tall, `--border-soft` base) with an `hbar-fill` (`--ink-soft` at rest, `--add` when selected), and a right-aligned mono value. Clickable rows (`hbar-row.clickable`) get a `--panel-sunken` hover fill and a `hbar-row.selected` row gets an `--add-bg` wash. Non-clickable variants (By tool, By agent, By model) omit the sign column and selection states entirely — the device is reserved for rows that actually filter something.

### Filter Chip
An `--add-bg`-filled, fully-rounded (12px) chip in `--add` mono text, holding the filter's label, a `+` glyph that plays a one-shot 900ms scale-flash (`@keyframes flash`) the instant a filter is applied — the same beat as a line landing in a diff — and a circular clear (`×`) button that reveals an `--add`-tinted hover ring.

### Icon Button
A 28×28px transparent button (`6px` radius, `1px` `--border`), `--ink-soft` icon color at rest; hover shifts border to `--ink-soft`, icon to `--ink`, and fills `--panel-sunken`. Used for the header's refresh action.

### Block Button
A full-width, transparent, `1px`-`--border` bordered button (`6px` radius, 12px mono `--ink` text) — used for "Show all N →" list-overflow actions. Same hover treatment as the icon button.

## Do's and Don'ts

### Do:
- **Do** keep diff-green (`--add`/`--add-line`/`--add-bg`) exclusive to connected/added/selected/up state, and diff-red (`--remove`/`--remove-line`/`--remove-bg`) exclusive to disconnected/error/removed/down state — never swap their roles or use either for decoration.
- **Do** route every measured value (cost, tokens, counts, durations, percentages, timestamps) through JetBrains Mono with tabular numerals and ligatures disabled.
- **Do** express elevation as a `--bg`/`--panel`/`--panel-sunken` surface-tone step plus a 1px border, never a `box-shadow`.
- **Do** reuse the `.hbar-sign` gutter device only on rows that actually drive a filter or selection; a purely informational ranked list (By tool, By agent, By model) omits it.
- **Do** ship both the light and dark palette together for any new screen in this world — this build's dark theme is a real, reviewed counterpart, not a stub.
- **Do** keep the wordmark text-only mono, no icon or logomark.

### Don't:
- **Don't** introduce a third saturated color, or a per-series channel-color set, into this world — the outgoing system's `--ch1`–`--ch4` convention does not carry forward; a multi-series need in a later screen should draw from the ink/gray scale, not a new hue set.
- **Don't** add `box-shadow`, blur, or card-elevation effects anywhere on this surface.
- **Don't** set an uppercase micro-label or a numeric/path value in the body sans — labels and readouts both stay in mono on this screen; only running prose (if any is added later) takes the sans face.
- **Don't** re-introduce font ligatures on any mono context.
- **Don't** color a bar, cell, or row to mean anything other than a diff-semantic state (connected/added/selected vs. disconnected/error/removed) — "today" on the bar chart, for example, is marked by tone (`--ink-soft`) rather than green, specifically to keep green meaning "selected/connected," not "current."
