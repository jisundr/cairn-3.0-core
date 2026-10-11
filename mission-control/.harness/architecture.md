## Stack
- Python 3.11+ — stdlib only (`sqlite3`, `http.server`), no runtime pip deps

## Layering
- No domain modules exist yet. `interfaces.py` defines the contracts a later phase implements, named after the components this repo will eventually hold: `db.py` (schema + insert helpers), `parser.py` (transcript walker), `pricing.py` (read-time cost lookup), `backfill.py` (cross-project backfill), `server.py` (stdlib HTTP + JSON API).
