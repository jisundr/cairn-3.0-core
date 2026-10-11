// Rough monospace-text width estimate (var(--mono), 12px) - good enough to
// place an inline SVG element (a value label, an info-mark) right after a
// text node without measuring the real rendered width, which an SVG <text>
// only exposes via getBBox() (unavailable in jsdom, and unnecessary
// precision for a few px of spacing).
const MONO_CHAR_WIDTH_PX = 6.4;

export function estimateTextWidth(text: string): number {
  return text.length * MONO_CHAR_WIDTH_PX;
}
