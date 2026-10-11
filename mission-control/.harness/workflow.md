## Gates
- `pytest` clean before any commit
- Frontend: `npm run build` and `npm test` inside `frontend/` clean before any commit
- Frontend: `npm run e2e` inside `frontend/` (builds, then runs `playwright test`) clean before any commit
- One artifact per commit

## Testing
- Frontend: `frontend/e2e/` (Playwright) against two `server.py` instances started by `playwright.config.ts` - "populated" (seeded by `e2e/fixtures/seed.py` via `db.py`'s insert helpers) and "cold-start" (an empty, never-seeded project root). Each fixture is a single `server.py` process: `vite.config.ts`'s `build.outDir` points at `../static`, which server.py's own static_dir route serves alongside its JSON API. `npm run build` must precede `playwright test` - server.py serves whatever's already in `static/`.
