# Setting up product docs

Cairn's product docs and their defaults: Brief `docs/product/BRIEF.md`, PRD `PRD.md`, User flow `USER-FLOW.md`, Architecture `ARCHITECTURE.md`, API `API.md`, Schema `SCHEMA.md`, Roadmap `ROADMAP.md`, all under `docs/product/`.

1. Look for an existing equivalent of each, by file name and headings (a `docs/requirements/product.md` with Features and Non-goals is a PRD). Skip `docs/tasks/`, `.harness/`, and impeccable's `docs/PRODUCT.md`/`docs/DESIGN.md`.
2. No match → default, no question. A match at the default path, or differing only in case → keep it, no question. A match elsewhere → one `AskUserQuestion` per doc: keep the current path, or adopt the default (move it there).
3. Under `.harness/workflow.md`'s `## Docs`, add one line per doc kept off its default: `- PRD: docs/requirements/product.md`. Defaults are not listed.
4. Ask once whether to copy the product-doc templates into `docs/product/_template/`. Nothing in cairn reads that copy; it is for people who want starting points. On yes, create it and copy `product/_template/` in, skipping any file already there. No answer → skip.
5. Report what was mapped and created. A re-run asks only about a doc not yet in the map.

Task docs (`docs/tasks/`, `REQUIREMENTS.md`, `PLAN.md`, `STATE.md`, `EPIC.md`) keep fixed names: `/cairn-triage` and mission-control parse them.
