import type { SVGProps } from "react";

// SVG-safe equivalent of InfoDot.tsx's `.info-dot` icon, for use inside a
// Recharts chart's SVG tree (HbarList, ProjectCostPanel) where InfoDot's own
// `<span>` wrapper isn't valid markup. Same shape, same default title -
// `screen.getByTitle(...)` finds this the same way it finds InfoDot's,
// since both carry a `title` DOM attribute.
interface ChartInfoMarkProps {
  x: number;
  y: number;
  title?: string;
}

// `SVGGElement`'s React props don't include `title` (SVG's own `<title>`
// child element is the standard way to label one, which is *also* rendered
// below) - `dom-testing-library`'s byTitle query only recognizes a bare
// `<title>` child when its parent is `<svg>` itself, never a nested `<g>`
// like this one, so the attribute is additionally set via this cast to
// match how `screen.getByTitle(...)` finds InfoDot.tsx's own `<span
// title=...>`.
const titleAttr = (title: string) => ({ title }) as SVGProps<SVGGElement>;

export function ChartInfoMark({ x, y, title = "Model not yet priced" }: ChartInfoMarkProps) {
  return (
    <g transform={`translate(${x}, ${y - 7})`} color="var(--ink-faint)" {...titleAttr(title)}>
      <title>{title}</title>
      <circle cx="7" cy="7" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <line x1="7" y1="6.5" x2="7" y2="10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="7" cy="4" r="0.6" fill="currentColor" />
    </g>
  );
}
