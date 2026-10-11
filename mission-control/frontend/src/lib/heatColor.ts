import { useEffect, useState } from "react";

// Extracted from ActivityHeatmap.tsx (F1) so ContributionCalendar (F7) can
// share the same green `--add` intensity scale rather than inventing a
// second color system for its own GitHub-style grid.

export interface HeatColors {
  add: string;
  border: string;
}

// `color-mix(in srgb, var(--add) X%, var(--border-soft))` is a CSS string,
// not usable inline on an SVG `fill` the same way - resolves both custom
// properties to concrete hex values once (light/dark-mode aware, since
// `getComputedStyle` reads whichever `@media (prefers-color-scheme)` block
// is active) and mixes in plain JS instead.
export function useHeatColors(): HeatColors {
  const [colors, setColors] = useState<HeatColors>({ add: "#2f8f49", border: "#ece9e1" });
  useEffect(() => {
    const styles = getComputedStyle(document.documentElement);
    const add = styles.getPropertyValue("--add").trim();
    const border = styles.getPropertyValue("--border-soft").trim();
    setColors({ add: add || "#2f8f49", border: border || "#ece9e1" });
  }, []);
  return colors;
}

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const match = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex.trim());
  if (!match) return null;
  return { r: parseInt(match[1], 16), g: parseInt(match[2], 16), b: parseInt(match[3], 16) };
}

export function mixHex(base: string, tint: string, t: number): string {
  const from = hexToRgb(base);
  const to = hexToRgb(tint);
  if (!from || !to) return t > 0 ? tint : base;
  const mix = (a: number, b: number) => Math.round(a + (b - a) * t);
  return `rgb(${mix(from.r, to.r)}, ${mix(from.g, to.g)}, ${mix(from.b, to.b)})`;
}
