# AI Trading Margin Visualizer

## App Prototype

This repository includes a runnable static dashboard for margin, liquidation, and paper-replay analysis.

Open [index.html](index.html) in a browser to use the app. The root page redirects to [ui/prototype/index.html](ui/prototype/index.html). No package install or build step is required for the prototype.

Current app features:

- Trade setup controls for asset, direction, equity, margin, entry, size, leverage, stop, maintenance margin, fees, AI confidence, and volatility shock.
- Health score, liquidation estimate, margin usage, and risk-to-stop metrics.
- Canvas risk map showing entry, stop, liquidation, and shock path.
- AI consensus panel for Quant, Neural, and Sentiment scores.
- Defensive AI rule: when a decision is ambiguous or risk signals conflict, the app favors protecting capital over taking more exposure.
- Local paper replay controls for run, pause, step, reset, and replay speed.
- Paper equity curve, open position state, simulated drawdown, and replay price tape.
- Decision log, mistake log, and strategy generation timeline to preview the future command center workflow.
- Strategy generation timeline now reads the Brain strategy API when it is available, with a local fallback when the API or database is down.
- Stress scenario table for favorable, adverse, stop, shock, and liquidation outcomes.
- Local snapshot log stored in browser storage.

Neural-Twin is a four-service framework for simulating, executing, and evolving trading strategies across crypto, stocks, commodities, and other asset classes. The system is designed around a controlled simulation loop: a Mirror service replays historical markets as if they are live, a Brain service makes paper-trading predictions and decisions, a Lab service proposes strategy improvements, and a UI service shows the current state of the system.

The core concept is to load historical market data, such as the last five years of stock candles, and make the Brain predict the next move as though the future is unknown. Because the replay is historical, the system can immediately score each prediction against what actually happened. Mistakes and correct calls become training evidence for the Lab, which asks an LLM or mock provider for a constrained rewrite of the active strategy version under `brain/versions/`, validates it in a sandbox, compares it against the baseline, and only promotes changes that clear the configured thresholds.

A typical training run should be able to replay many assets many times. For example, ten stocks with five years of candles can be run through three passes. Each pass records predictions, actual outcomes, drawdown, paper equity, and mistakes. The Lab then decides whether to hold the current strategy or queue a candidate rewrite at a checkpoint. Production strategy code should not be rewritten after every candle; it should be rewritten, tested, compared, and promoted through a controlled validation gate.

This repository now contains the planned service folders, configuration files, database schema, a sample historical fixture, and minimal runnable skeletons for the Mirror, Brain, Lab, and UI.

## Current Implementation Reality

The repo now has a functioning Lab and strategy-history API, but the runtime app is still a mixed prototype rather than the full four-service architecture described below.

- The current browser UI is the static prototype under `ui/prototype/`, not a Vue app yet.
- The strategy timeline is backed by the Brain API.
- The replay tape, decision log, and mistake log are still generated locally in the browser.
- Mirror exists as a replay REST service, but the UI does not consume it yet.
- The Docker `brain` service currently runs the read-only API, not a persistent decision engine.

See [Current State Review](docs/CURRENT_STATE_REVIEW.md) for the full drift and refactor notes.

## Operating Notes

- The system should learn from every right and wrong prediction, but it should not rewrite production strategy code after every candle. Strategy changes should happen through checkpointed evolution: collect evidence, generate a candidate, sandbox it, compare it against the baseline, and promote it only when validation improves.
- Live stock trading is a later stage, not the default mode. A strategy that performs well on historical replay must still pass paper trading, audit logging, out-of-sample testing, broker risk limits, rollback controls, and manual approval before live execution is enabled.

## Core Philosophy

- The Two-Sided Coin: the Mirror service makes historical market data look live so the Brain can be tested without changing its execution model.
- Ensemble Consensus: no single indicator should trigger a trade. Decisions require agreement across Quant, Neural, and Sentiment signals.
- Genetic Evolution: when the Brain performs poorly, the Lab asks a local or remote LLM to rewrite a constrained strategy surface, tests it in a sandbox, and only promotes the change if benchmarks improve.
- Decoupled Services: the Lab may rewrite Brain strategy code, but the Mirror and UI remain isolated from those changes.
- Persistence First: simulation clock, portfolio state, market data, mistakes, and strategy versions must survive restarts.

## Strategy Versioning

Promoted strategies are versioned explicitly. The system does not auto-select the newest file on disk.

- `brain/strategy.py` is a stable loader and import target for the rest of the app.
- `brain/versions/strategy_gNNNN.py` stores immutable promoted strategy versions.
- `config/active_strategy.json` is the default active strategy pointer.
- `ACTIVE_STRATEGY_GENERATION` in `.env` is an override for testing and replay.

Selection order is:

1. `ACTIVE_STRATEGY_GENERATION` if set
2. `config/active_strategy.json`
3. fallback `g0001`

This keeps runs reproducible across machines and Git checkouts. Do not treat "latest modified file" as the active strategy.

## Planned Service Map

```text
/neural-twin
|-- .env                # Local secrets and provider choices, never committed
|-- .env.template       # Safe config template committed to Git
|-- .gitignore          # Keeps data, secrets, and generated artifacts out of Git
|-- docker-compose.yml  # Orchestrates all services
|-- brain/              # Service 1: Python trading execution
|   |-- main.py         # Trading loop
|   |-- api_server.py   # Read-only strategy history API
|   |-- db.py           # Postgres reads with local fallback
|   |-- strategy.py     # Stable loader for the active strategy version
|   |-- strategy_registry.py # Active generation resolution and version registry
|   |-- versions/       # Immutable promoted strategy generations
|   |-- ensemble.py     # Quant, neural, and sentiment consensus math
|   `-- requirements.txt
|-- config/
|   `-- active_strategy.json # Default active generation pointer
|-- mirror/             # Service 2: Node.js market simulator
|   |-- server.js       # WebSocket and REST API
|   |-- engine.js       # Playback, pause, and skip controls
|   `-- data/           # Historical CSV/Parquet files, ignored by Git
|-- lab/                # Service 3: Python evolution engine
|   |-- db_sync.py      # Postgres write-side sync for promotions
|   |-- evolver.py      # LLM interface and Git manager
|   |-- trainer.py      # Multi-asset, multi-pass historical training loop
|   |-- continuous_runner.py # Stop-file-controlled continuous training orchestrator
|   |-- compare.py      # Baseline vs candidate evaluation
|   |-- promote.py      # Gated strategy promotion with backup manifest
|   |-- sandbox.py      # Isolated test runner
|   `-- prompts.py      # Code-generation prompts and policies
|-- ui/                 # Service 4: Vue command center
|   |-- src/            # Vue components and Pinia stores
|   `-- tailwind.config.js
|-- db/                 # Persistent storage setup
|   `-- init.sql        # Multi-asset schema
|-- data/
|   `-- fixtures/       # Tiny committed fixture for smoke tests
`-- docs/               # Project design and implementation notes
```

## Quick Start

Run the static UI prototype:

```bash
open index.html
```

Run the first historical prediction backtest:

```bash
python brain/main.py --data data/fixtures/sample_stock_ohlcv.csv
```

Run the Brain strategy history API used by the prototype timeline:

```bash
python brain/api_server.py
```

Fetch delayed watchlist predictions from the Brain API:

```bash
curl "http://localhost:3201/watchlist/predictions?symbols=AMZN,NVDA,GOOG"
```

Inspect the local demo broker state:

```bash
curl "http://localhost:3201/broker/demo/state"
```

Run three historical training passes across every CSV in a data directory:

```bash
python lab/trainer.py --data-dir data/fixtures --passes 3 --report run/latest_training_report.json
```

Run a benchmark pack:

```bash
python lab/trainer.py --benchmark benchmarks/us-large-cap-daily-v1.json
```

Benchmark packs are committed JSON files that define a reproducible symbol set, data directory, thresholds, and replay parameters.

Run the stop-file-controlled continuous historical loop:

```bash
python lab/continuous_runner.py --data-dir data/historical --passes 3 --interval-seconds 3600
```

Create `run/STOP` to stop the loop cleanly. Create `run/PAUSE` to pause it without exiting, then remove `run/PAUSE` to resume.

Import five years of daily stock OHLCV into ignored historical CSV files:

```bash
python data/import_stocks.py --symbols AAPL,MSFT,NVDA,AMZN,GOOGL --years 5 --out data/historical
```

You can replace the `--symbols` list with any comma-separated stock symbols you want to import. Examples:

```bash
python data/import_stocks.py --symbols TSLA,META,NFLX --years 5 --out data/historical
python data/import_stocks.py --symbols JPM,GS,BAC --years 10 --out data/historical
python data/import_stocks.py --symbols KO,PEP,PG,WMT --years 3 --out data/historical
```

The importer writes one CSV per symbol, named `<SYMBOL>.csv`, into the output directory.

The importer uses `yfinance`. If it is not installed yet:

```bash
python -m pip install yfinance
```

When a run queues a rewrite, `lab/trainer.py` now writes the current training report, generates a candidate from the active strategy version, compares it against the current strategy, and auto-promotes only when the comparison verdict is `promote_candidate`. Promotion writes a new immutable `brain/versions/strategy_gNNNN.py` file and updates `config/active_strategy.json`. Use `--no-auto-promote` if you want the trainer to stop after verdicting.

`lab/continuous_runner.py` wraps that same trainer/evolver/compare/promote chain in a local loop. It does not bypass the gates. A rejected candidate is a healthy result, not a failure. The current five-symbol historical run is a good example: the candidate was rejected because drawdown got worse, so promotion was correctly skipped.

When Postgres is available, promotion also upserts the promoted generation into `strategy_generations` and marks it active there. The Brain API reads Postgres for strategy history, but falls back to local config and version files if the database is unavailable.

Generate a Lab rewrite candidate:

```bash
python lab/evolver.py --mistakes run/latest_training_report.json --strategy brain/strategy.py
```

Passing `--strategy brain/strategy.py` is still valid. The evolver resolves that loader to the active version file before building the rewrite prompt.

Compare the current strategy to the latest candidate:

```bash
python lab/compare.py --data-dir data/fixtures --candidate lab/candidates/strategy_candidate.py --passes 3 --report run/latest_comparison_report.json
```

Promote a winning candidate manually:

```bash
python lab/promote.py --candidate lab/candidates/strategy_candidate.py --comparison-report run/latest_comparison_report.json
```

Manual promotion creates the next `brain/versions/strategy_gNNNN.py`, updates `config/active_strategy.json`, and writes a local promotion manifest under `run/promotions/`.

Run the service stack target:

```bash
cp .env.template .env
docker-compose up --build
```

`.env.template` is organized into a small required section for the default local Onyx setup and a larger optional override section for model, strategy, runtime, and database overrides.

For a real model-backed rewrite run, set `LLM_PROVIDER=onyx` and configure `ONYX_BASE_URL`, `ONYX_MODEL`, plus either `ONYX_TOKEN` or `ONYX_KEY` and `ONYX_SECRET` in `.env`. The default `mock` provider stays useful for offline development.

For your self-hosted Onyx app running at `http://localhost:3000`, use:

```bash
LLM_PROVIDER=onyx
ONYX_BASE_URL=http://localhost:3000
ONYX_API_MODE=app
ONYX_TOKEN=your_onyx_api_key
```

If your Onyx admin has a default text model configured, you can leave `ONYX_MODEL` blank. If you want to override the model per request, set `ONYX_MODEL` to the actual underlying model version configured in Onyx, not a generic label like `onyx-chat`.

When the Lab runs inside Docker, use `http://host.docker.internal:3000` instead of `http://localhost:3000` so the container can reach your host machine.

## Reproducible Onyx + Ollama Setup

This is the exact local topology that was verified to work for this repository:

```text
Repo scripts -> Onyx API at http://localhost:3000
Onyx backend -> Ollama at http://host.docker.internal:11434
Ollama models stored under %USERPROFILE%\.ollama\models
```

The repo does not talk to Ollama directly. The repo talks to Onyx. Onyx talks to Ollama.

### 1. Install and verify Ollama on Windows

Install Ollama on the Windows host. If `ollama` is not on your `PATH`, the default binary is typically:

```powershell
C:\Users\<your-user>\AppData\Local\Programs\Ollama\ollama.exe
```

Pull a coding model:

```powershell
& 'C:\Users\<your-user>\AppData\Local\Programs\Ollama\ollama.exe' pull qwen2.5-coder:7b
```

Verify the model is available:

```powershell
& 'C:\Users\<your-user>\AppData\Local\Programs\Ollama\ollama.exe' list
```

Or verify the Ollama HTTP API directly:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
```

Expected result: `qwen2.5-coder:7b` appears in the model list.

### 2. Run Onyx

Run Onyx locally. The verified setup here used Docker and exposed Onyx on:

```text
http://localhost:3000
```

If Onyx is running in Docker, do not point it at `127.0.0.1:11434` for Ollama. Inside the container, `127.0.0.1` is the container itself, not the Windows host.

### 3. Configure Ollama inside Onyx

In Onyx:

1. Open `Admin -> Language Models`
2. Add provider: `Ollama`
3. Use the Ollama base URL:

```text
http://host.docker.internal:11434
```

Use `http://localhost:11434` only if Onyx itself is running directly on Windows rather than in Docker.

4. Click `Fetch Available Models`
5. Confirm `qwen2.5-coder:7b` appears
6. Save the provider
7. Set `qwen2.5-coder:7b` as the default text model

### 3a. Re-check Onyx settings after Docker startup

If Onyx is started, restarted, or recreated with Docker, re-open `Admin -> Language Models` before running the Lab and confirm:

1. The Ollama provider still exists
2. The Ollama base URL is still:

```text
http://host.docker.internal:11434
```

3. `qwen2.5-coder:7b` still appears in the fetched model list
4. `qwen2.5-coder:7b` is still the default text model

Do not assume `127.0.0.1:11434` will work from Onyx when Onyx is running in Docker. That address only points back to the container itself.

### 4. Create the Onyx service account key

In Onyx:

1. Open `Admin -> Integrations -> Service Accounts`
2. Generate a service account key
3. Keep that key for the repo `.env`

### 5. Configure the repository `.env`

Create `.env` in the repo root:

```text
C:\laragon\www\dotnet\AI-Trading-Margin-Visualizer\.env
```

Recommended contents:

```bash
LLM_PROVIDER=onyx
ONYX_BASE_URL=http://localhost:3000
ONYX_API_MODE=app
ACTIVE_STRATEGY_GENERATION=
ONYX_MODEL=
ONYX_TOKEN=your_service_account_key
```

Important notes:

- Keep `ONYX_MODEL=` blank if Onyx already has a default text model configured.
- Keep `ACTIVE_STRATEGY_GENERATION=` blank in normal operation so the repo uses `config/active_strategy.json`.
- Set `ACTIVE_STRATEGY_GENERATION=g0002` only when you want to pin a specific promoted version for testing.
- Do not put the Ollama URL in the repo `.env`. The repo should point to Onyx, not Ollama.
- `.env` is ignored by Git in this repository.

### 5a. Existing Postgres volumes

If you already have a persisted `pgdata` volume from an older version of the repo, the new `strategy_generations` columns and indexes in [db/init.sql](db/init.sql) will not be applied automatically. Either:

1. recreate the Postgres volume, or
2. run the `ALTER TABLE` and `CREATE INDEX` statements from [db/init.sql](db/init.sql) manually against the existing database.

### 6. Verify the full chain

Run:

```powershell
python lab/evolver.py --provider onyx --mistakes run/latest_training_report.json --strategy brain/strategy.py
```

Expected result:

```json
{
  "provider": "onyx",
  "candidate": "lab\\candidates\\strategy_candidate.py",
  "status": "candidate_written"
}
```

That confirms this chain is working:

```text
repo script -> Onyx -> Ollama -> candidate file written
```

Current Mirror endpoints:

- `GET /health`
- `GET /status`
- `GET /candles`
- `GET /step?count=1`
- `GET /pause`
- `GET /resume`
- `GET /reset`

Current Brain endpoints:

- `GET /health`
- `GET /strategy/active`
- `GET /strategy/history?limit=8`
- `GET /watchlist/predictions?symbols=AMZN,NVDA,GOOG`
- `GET /broker/demo/state`
- `POST /broker/demo/order`

The Brain API prefers Postgres-backed strategy history and active-generation metadata, but it falls back to `config/active_strategy.json` plus local `brain/versions/` files when the database is unavailable.

## Continuous Historical Training

Use `lab/continuous_runner.py` when you want repeated historical training without manually re-running the trainer.

Example:

```powershell
python lab\continuous_runner.py --data-dir data\historical --passes 3 --interval-seconds 3600
```

Using a benchmark pack:

```powershell
python lab\continuous_runner.py --benchmark benchmarks\us-large-cap-daily-v1.json --interval-seconds 3600
```

Optional automatic data refresh before each cycle:

```powershell
python lab\continuous_runner.py --passes 3 --interval-seconds 3600 --import-symbols AAPL,MSFT,NVDA,AMZN,GOOGL --import-years 5
```

Control files:

- `run/continuous.lock`: prevents overlapping continuous runners
- `run/continuous_status.json`: latest runner state, last cycle summary, and next wake-up time
- `run/STOP`: when this file exists, the runner exits cleanly after the current check
- `run/PAUSE`: when this file exists, the runner stays alive but does not start a new cycle

Important behavior:

- The continuous runner calls `lab/trainer.py`; it does not invent a second training path.
- Trainer auto-evolution still follows the same rules: generate candidate, compare candidate, promote only on `promote_candidate`.
- `reject_candidate` and `hold_for_review` are expected outcomes. They mean the gates worked.
- The runner stops after `CONTINUOUS_MAX_CONSECUTIVE_FAILURES` failed cycles unless you raise that limit.
- This loop is for historical training and paper evolution only. It must not be treated as permission for live trading.

## Benchmark Packs And Contribution Artifacts

Benchmark packs live under `benchmarks/` and give contributors a shared way to run the same symbol set, date source, and thresholds.

Current example:

- [benchmarks/us-large-cap-daily-v1.json](benchmarks/us-large-cap-daily-v1.json)

When you run `lab/trainer.py` with `--benchmark`, the trainer now writes a contribution artifact under `run/contributions/` by default. That artifact is a compact shareable record of:

- benchmark name
- strategy generation
- final metrics
- candidate verdict
- promotion status
- report paths

This is intended for sharing reproducible results and validation evidence without committing local `.env` secrets or raw runtime noise.

## Initial Documentation

- [Architecture](docs/ARCHITECTURE.md): service boundaries, data flow, and safe-rewrite model.
- [Current State Review](docs/CURRENT_STATE_REVIEW.md): what is real today, what is still prototype-only, and what needs refactoring.
- [Engineering Playbook](docs/PLAYBOOK.md): environment, local debugging, config, database, and market data notes.
- [Evolution Workflow](docs/EVOLUTION_WORKFLOW.md): LLM strategy rewriting, sandbox tests, Git promotion, and rollback.
- [Operations And Live Trading](docs/OPERATIONS_AND_LIVE_TRADING.md): how to run continuous training now, what is needed for live prediction, and how a future eToro broker path should be staged.
- [TODO](docs/TODO.md): prioritized implementation backlog from persistence through broker integration.
- [UX Storyboard](docs/UX_STORYBOARD.md): first-run, failure, evolution, and deployment scenes.
- [Implementation Backlog](docs/IMPLEMENTATION_BACKLOG.md): suggested build order for the first runnable version.
- [Setup](setup.md): practical startup and verification checklist for Docker, Onyx, Ollama, and repo commands.

## Safety Position

This project should begin as a paper-trading and simulation system only. Live exchange execution should remain disabled until the Brain has explicit risk limits, audit logs, rollback controls, test coverage, out-of-sample validation, and manual approval gates. A strategy that performs well on historical replay is still not proven safe for live trading.

## Next Implementation Step

Replace the small committed fixture with a real five-year historical data adapter for multiple symbols, then persist predictions, decisions, mistake logs, and backtest runs so the UI can stop using local replay-only event history.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Community Terms

Contributors and users are expected to be respectful, constructive, and safety-conscious. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Disclaimer

This project is experimental trading software. It is not financial advice, has no warranty, and must be used at your own risk. See [DISCLAIMER.md](DISCLAIMER.md).
