# Implementation Backlog

This backlog turns the documentation pack into a runnable v1 in conservative steps.

## Phase 1: Repository Scaffolding

- Add `.gitignore`.
- Add `.env.template`.
- Add `docker-compose.yml`.
- Create `brain/`, `mirror/`, `lab/`, `ui/`, `db/`, and `data/historical/` folders.
- Add placeholder Dockerfiles for Brain, Mirror, Lab, and UI.
- Add `db/init.sql` with the multi-asset schema.

## Phase 2: Mirror MVP

- Load a small CSV fixture from `data/historical/`.
- Stream candles over WebSocket.
- Expose REST endpoints for pause, resume, skip, reset, and status.
- Support terminal `Space`, `Enter`, and `Ctrl+C` controls.
- Add deterministic replay mode for tests.

## Phase 3: Brain MVP

- Subscribe to Mirror WebSocket events.
- Implement simple ensemble scoring with Quant, Neural placeholder, and Sentiment placeholder signals.
- Emit paper decisions only.
- Persist decisions, PnL, and state to Postgres.
- Add graceful shutdown state save.

## Phase 4: Lab MVP

- Read mistake logs and current strategy code.
- Implement mock LLM provider for tests.
- Implement Ollama provider.
- Save candidates under ignored `lab/candidates/`.
- Validate candidate syntax and interface.
- Run sandbox replay against Mirror deterministic mode.
- Commit approved changes to Git.

## Phase 5: UI MVP

- Show simulation clock, status, and current asset.
- Show price chart and equity curve.
- Show positions and decision log.
- Show mistake log table.
- Show strategy generation timeline.

## Phase 6: Safety Hardening

- Add candidate execution timeouts.
- Add blocked import checks for generated code.
- Add daily evolution attempt limits.
- Add max drawdown, max position size, and max trade frequency rules.
- Add rollback flow using `git revert`.
- Add audit trail tables for candidate tests and strategy promotions.

## Phase 7: Asset Expansion

- Add stock data adapter and `stock_metrics` ingestion.
- Add crypto metrics adapter and `crypto_metrics` ingestion.
- Add commodity metrics adapter and `commodity_metrics` ingestion.
- Add asset-specific ensemble modules.

## First Code Task Recommendation

Start with Phase 1. The first concrete files should be:

- `.gitignore`
- `.env.template`
- `docker-compose.yml`
- `db/init.sql`

After that, build a Mirror MVP with a tiny sample CSV so the Brain has a deterministic data source from day one.
