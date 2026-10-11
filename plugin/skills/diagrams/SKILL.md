---
name: diagrams
description: Text-source diagrams rendered to SVG. Loaded by scribe when a doc needs a picture.
---

# cairn:diagrams

## When a diagram earns its place

A flow with branches, loops, or more than one actor; a layout where position carries meaning — components and what calls what. A straight run of five or fewer steps, or items with no relations between them, is a list: write the list instead.

## Pick the source

- **Flows, sequences, states, decisions** → Mermaid: `<name>.mmd`, rendered to `<name>.svg` beside it.
- **Layout-heavy architecture** Mermaid can't place well → `<name>.gen.mjs`, a dependency-free Node script that writes `<name>.svg`.

Both live in a `diagrams/` folder beside the doc that shows them. The SVG is output: to change the picture, edit the source and re-render, not the SVG. A PNG copy, only for a target that can't show SVG, is converted from the SVG, sits beside it, and is re-rendered with it.

## Look and feel

Colors, fonts and spacing come from the project's design system when it has one — `docs/DESIGN.md`'s frontmatter tokens, or the token file the project names. Mermaid gets them through `diagrams/mermaid.config.json` (`theme: base`, `themeVariables`, passed with `-c`); generator scripts import them from one shared `diagrams/theme.mjs`. No design system → the neutral palette in `reference/starters.md`, in those same two files. Starters for all three files are there too. Every diagram gets a solid background, so it reads on a dark page.

## Facts in the picture

Labels use the names the code and the doc text use, and nothing the text doesn't say. A rename or a changed step updates the source, the SVG and the prose in the same edit.

## In the doc

Each diagram links its SVG, with alt text saying what it shows, and carries a one-line regenerate note directly under it:

```markdown
![Checkout: request validated, then queued](diagrams/checkout.svg)
<!-- regenerate: mmdc -i diagrams/checkout.mmd -o diagrams/checkout.svg -c diagrams/mermaid.config.json -b white -->
```

A generator diagram's note is `<!-- regenerate: node diagrams/<name>.gen.mjs -->`.

## Render and check

`scribe` has no `Bash`, so it writes the sources and the doc, then hands back each regenerate command with the paths it wrote; the main thread runs them. After any render — or in review — run `stale.sh` from this skill's base directory, from the project root: `bash <base>/stale.sh docs`. It names every SVG older than its source (last commit time; an uncommitted source edit counts as newer) or never rendered, and exits 1 if any. A render that can't run — no Node, no Chromium for `mmdc` — is reported as not rendered; a hand-drawn SVG is no substitute.
