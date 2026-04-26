# Implementation Backlog

This backlog turns the documentation pack into a runnable v1 in conservative steps.

## Phase 1: Repository Scaffolding

- [x] Add `.gitignore`.
- [x] Add `.env.template`.
- [x] Add `docker-compose.yml`.
- [x] Create `brain/`, `mirror/`, `lab/`, `ui/`, `db/`, and `data/` folders.
- [x] Add Dockerfiles for Brain, Mirror, and Lab.
- [x] Add static UI prototype under `ui/prototype/`.
- [x] Add `db/init.sql` with multi-asset, prediction, mistake, generation, and backtest tables.
- [x] Add a tiny committed fixture under `data/fixtures/` for smoke tests.

## Phase 2: Mirror MVP

- [x] Load a small CSV fixture from `data/fixtures/`.
- [ ] Stream candles over WebSocket.
- [x] Expose REST endpoints for pause, resume, step, reset, candles, and status.
- Support terminal `Space`, `Enter`, and `Ctrl+C` controls.
- Add deterministic replay mode for tests.

## Phase 3: Brain MVP

- Subscribe to Mirror WebSocket events.
- [x] Implement simple ensemble scoring with Quant, Neural placeholder, and Sentiment placeholder signals.
- [x] Run a historical next-candle prediction backtest against a CSV fixture.
- [x] Expose a read-only Brain API for active strategy state and generation history.
- [x] Expose basic live-watch and demo broker scaffolding from the Brain API.
- Emit paper decisions only.
- Persist decisions, PnL, and state to Postgres.
- Add graceful shutdown state save.

## Phase 4: Lab MVP

- [x] Read mistake logs and current strategy code.
- [x] Implement mock LLM provider for tests.
- [x] Add multi-asset, multi-pass historical training loop.
- [x] Implement Onyx provider skeleton.
- [x] Save candidates under ignored `lab/candidates/`.
- [x] Validate candidate syntax and interface.
- [x] Compare baseline vs candidate and return a verdict.
- [x] Promote passing candidates into immutable `brain/versions/strategy_gNNNN.py` files.
- [x] Persist promoted generation metadata and active state to Postgres when available.
- [x] Add a continuous historical runner with stop, pause, lock, and status files.
- [x] Add committed benchmark packs and contribution artifacts for reproducible shared evaluation.
- Run sandbox replay against Mirror deterministic mode.
- Commit approved changes to Git.

## Phase 5: UI MVP

- [x] Show simulation clock, status, and current asset.
- [x] Show price chart and equity curve.
- [x] Show positions and decision log.
- [x] Show mistake log table.
- [x] Show strategy generation timeline.
- [x] Read strategy generation timeline from the Brain API when available, with local fallback.
- Add broker notification log for demo/live order events.

## Phase 6: Safety Hardening

- Add candidate execution timeouts.
- Add blocked import checks for generated code.
- Add daily evolution attempt limits.
- Add max drawdown, max position size, and max trade frequency rules.
- Add rollback flow using `git revert`.
- Add audit trail tables for candidate tests and strategy promotions.

## Phase 7: Asset Expansion

- [x] Add stock data adapter and `stock_metrics` ingestion.
- Add crypto metrics adapter and `crypto_metrics` ingestion.
- Add commodity metrics adapter and `commodity_metrics` ingestion.
- Add asset-specific ensemble modules.

## First Code Task Recommendation

The repository has moved past the initial scaffolding pass. The next concrete task should be:

- Add a real stock data adapter that writes five-year daily OHLCV CSV files into ignored `data/historical/`.
- Teach Mirror to replay files from `data/historical/` by symbol and date range.
- Persist Brain backtest predictions and mistake logs into Postgres.
- Persist decisions and backtest runs into Postgres.
- Persist broker notification events and audit trail into Postgres.
- Replace the remaining local replay-only decision and mistake UI history with database-backed records.

That gives the Lab real evidence for deciding whether a rewrite made the strategy better or just overfit the sample, and it moves the UI from prototype-only event history to real run history.

## Refactor Priority

Before adding much more UI behavior, reduce the current architecture drift:

- Move replay state generation out of `ui/prototype/assets/app.js` and into Mirror.
- Make the UI consume Mirror and Brain APIs instead of fabricating replay, decision, and mistake events locally.
- Keep `ui/prototype/` as the active prototype until a real Vue UI exists, rather than documenting both as if both are current.
- Remove root-level artifacts that are no longer serving a project, such as a root `package-lock.json` without a matching root `package.json`.
