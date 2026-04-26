# TODO

This is the current implementation TODO, ordered by practical priority.

## 1. Persist real run data

- Persist predictions to Postgres
- Persist paper decisions to Postgres
- Persist mistake logs to Postgres
- Persist backtest runs to Postgres
- Persist broker notification events to Postgres
- Replace remaining UI-local event history with database-backed reads

## 2. Finish live watch mode

- Add a real UI panel for `/watchlist/predictions`
- Show current paper decisions for the active watchlist
- Show cooldown-aware `execution_guardrails` so blocked trades are visible as risk controls, not missing actions
- Add refresh cadence and stale-data handling
- Add symbol normalization for non-U.S. exchange symbols and broker aliases

## 3. Finish demo broker mode

- Add demo broker UI controls
- Add per-symbol max allocation limits
- Add max daily loss and cooldown rules
- Add explicit close-position workflow
- Add operator-facing broker notification log
- Persist demo broker audit trail and notification log in Postgres instead of only `run/demo_broker_state.json`

## 4. Broker integration

- Add eToro demo adapter
- Add instrument ID resolution and watchlist sync
- Add read-only broker account sync
- Add demo order placement path
- Add real mode only after demo mode is stable and audited

## 5. Market and event features

- Add company news ingestion
- Add earnings calendar ingestion
- Add macroeconomic series ingestion
- Add timestamp-safe historical event features
- Re-run benchmark comparisons with exogenous features enabled

## 6. Mirror and UI refactor

- Move replay state generation out of `ui/prototype/assets/app.js`
- Make UI read Mirror and Brain APIs instead of fabricating replay state
- Decide whether `ui/prototype/` remains the long-term UI or is replaced by a real Vue app

## 7. Community evaluation

- Persist contribution manifests to Postgres
- Add benchmark results view in UI
- Add import/export flow for contribution artifacts
- Add leaderboard view by generation and benchmark
