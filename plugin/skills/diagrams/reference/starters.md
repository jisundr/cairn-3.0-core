# Diagram starters

Copy into the doc's `diagrams/` folder and edit. With a design system, replace every value below with its token; without one, this neutral palette is the default, kept in exactly these two files.

## `mermaid.config.json`

Passed to every Mermaid render with `-c`; `-b` takes the same background.

```json
{
  "theme": "base",
  "themeVariables": {
    "background": "#ffffff",
    "primaryColor": "#f4f5f7",
    "primaryBorderColor": "#5b6472",
    "primaryTextColor": "#1f2328",
    "lineColor": "#5b6472",
    "secondaryColor": "#e8effc",
    "tertiaryColor": "#ffffff",
    "fontFamily": "system-ui, -apple-system, Segoe UI, sans-serif",
    "fontSize": "14px"
  }
}
```

Render: `mmdc -i diagrams/<name>.mmd -o diagrams/<name>.svg -c diagrams/mermaid.config.json -b white`. Without a global `mmdc`, `npx -y --package=@mermaid-js/mermaid-cli mmdc` runs the same command; it fetches a headless Chromium on first use.

## `theme.mjs`

Shared constants every generator script imports — no hex value appears in a `.gen.mjs` itself.

```js
// One place for diagram look and feel; values from the design system, or this neutral default.
export const theme = {
  bg: '#ffffff', surface: '#f4f5f7', stroke: '#5b6472', text: '#1f2328', accent: '#2f6fde',
  font: "system-ui, -apple-system, 'Segoe UI', sans-serif", fontSize: 14, unit: 8,
};
```

## `<name>.gen.mjs`

Dependency-free: `node:` built-ins only. Boxes sit on a grid; edges run box to box. Extend the arrays, not the drawing code, for most changes.

```js
// Regenerate: node diagrams/arch.gen.mjs — writes arch.svg beside this file.
import { writeFileSync } from 'node:fs';
import { theme as t } from './theme.mjs';

// Labels spell names the way the code does. Grid units: x/y in columns/rows.
const boxes = [
  { id: 'api', label: 'api/', x: 0, y: 0 },
  { id: 'queue', label: 'jobs queue', x: 1, y: 0 },
  { id: 'worker', label: 'worker/', x: 2, y: 0 },
];
const edges = [['api', 'queue'], ['queue', 'worker']];

const u = t.unit, w = 20 * u, h = 7 * u, gap = 6 * u, pad = 3 * u;
const pos = Object.fromEntries(boxes.map(b => [b.id, { x: pad + b.x * (w + gap), y: pad + b.y * (h + gap) }]));
const W = pad * 2 + Math.max(...boxes.map(b => b.x + 1)) * (w + gap) - gap;
const H = pad * 2 + Math.max(...boxes.map(b => b.y + 1)) * (h + gap) - gap;
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" font-family="${esc(t.font)}" font-size="${t.fontSize}">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${t.stroke}"/></marker></defs>
<rect width="100%" height="100%" fill="${t.bg}"/>
${edges.map(([a, b]) => { const p = pos[a], q = pos[b];
  return `<line x1="${p.x + w}" y1="${p.y + h / 2}" x2="${q.x}" y2="${q.y + h / 2}" stroke="${t.stroke}" stroke-width="1.5" marker-end="url(#arrow)"/>`; }).join('\n')}
${boxes.map(b => { const p = pos[b.id];
  return `<rect x="${p.x}" y="${p.y}" width="${w}" height="${h}" rx="${u}" fill="${t.surface}" stroke="${t.stroke}"/>
<text x="${p.x + w / 2}" y="${p.y + h / 2}" fill="${t.text}" text-anchor="middle" dominant-baseline="central">${esc(b.label)}</text>`; }).join('\n')}
</svg>
`;
writeFileSync(new URL('./arch.svg', import.meta.url), svg);
```
