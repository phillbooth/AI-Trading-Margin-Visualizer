# TODO

This is the current implementation TODO, ordered by practical priority.

## 1. Persist real run data

- [x] Persist predictions to Postgres (trainer report sync path)
- [x] Persist paper decisions to Postgres (trainer report sync path)
- [x] Persist mistake logs to Postgres (trainer report sync path)
- [x] Persist backtest runs to Postgres (trainer report sync path)
- [x] Persist broker notification events to Postgres (demo broker sync path)
- [x] Replace remaining UI-local event history with database-backed reads for decision/mistake/broker notification panels in the prototype (with local fallback)

## 2. Finish live watch mode

- [x] Add a real UI panel for `/watchlist/predictions`
- [x] Show current paper decisions for the active watchlist
- [x] Show cooldown-aware `execution_guardrails` so blocked trades are visible as risk controls, not missing actions
- [x] Add refresh cadence and stale-data handling
- Add symbol normalization for non-U.S. exchange symbols and broker aliases

## 3. Finish demo broker mode

- Add demo broker UI controls
- Add per-symbol max allocation limits
- Add max daily loss and cooldown rules
- Add explicit close-position workflow
- [x] Add operator-facing broker notification log (Brain endpoint + prototype panel)
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
