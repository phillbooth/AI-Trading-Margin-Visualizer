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
- Stress scenario table for favorable, adverse, stop, shock, and liquidation outcomes.
- Local snapshot log stored in browser storage.

Neural-Twin is a four-service framework for simulating, executing, and evolving trading strategies across crypto, stocks, commodities, and other asset classes. The system is designed around a controlled simulation loop: a Mirror service replays historical markets as if they are live, a Brain service makes paper-trading predictions and decisions, a Lab service proposes strategy improvements, and a UI service shows the current state of the system.

The core concept is to load historical market data, such as the last five years of stock candles, and make the Brain predict the next move as though the future is unknown. Because the replay is historical, the system can immediately score each prediction against what actually happened. Mistakes and correct calls become training evidence for the Lab, which asks an LLM or mock provider for a constrained rewrite of `brain/strategy.py`, validates it in a sandbox, and only promotes changes that improve backtest results.

A typical training run should be able to replay many assets many times. For example, ten stocks with five years of candles can be run through three passes. Each pass records predictions, actual outcomes, drawdown, paper equity, and mistakes. The Lab then decides whether to hold the current strategy or queue a candidate rewrite at a checkpoint. Production strategy code should not be rewritten after every candle; it should be rewritten, tested, compared, and promoted through a controlled validation gate.

This repository now contains the planned service folders, configuration files, database schema, a sample historical fixture, and minimal runnable skeletons for the Mirror, Brain, Lab, and UI.

## Operating Notes

- The system should learn from every right and wrong prediction, but it should not rewrite production strategy code after every candle. Strategy changes should happen through checkpointed evolution: collect evidence, generate a candidate, sandbox it, compare it against the baseline, and promote it only when validation improves.
- Live stock trading is a later stage, not the default mode. A strategy that performs well on historical replay must still pass paper trading, audit logging, out-of-sample testing, broker risk limits, rollback controls, and manual approval before live execution is enabled.

## Core Philosophy

- The Two-Sided Coin: the Mirror service makes historical market data look live so the Brain can be tested without changing its execution model.
- Ensemble Consensus: no single indicator should trigger a trade. Decisions require agreement across Quant, Neural, and Sentiment signals.
- Genetic Evolution: when the Brain performs poorly, the Lab asks a local or remote LLM to rewrite a constrained strategy surface, tests it in a sandbox, and only promotes the change if benchmarks improve.
- Decoupled Services: the Lab may rewrite Brain strategy code, but the Mirror and UI remain isolated from those changes.
- Persistence First: simulation clock, portfolio state, market data, mistakes, and strategy versions must survive restarts.

## Planned Service Map

```text
/neural-twin
|-- .env                # Local secrets and provider choices, never committed
|-- .env.template       # Safe config template committed to Git
|-- .gitignore          # Keeps data, secrets, and generated artifacts out of Git
|-- docker-compose.yml  # Orchestrates all services
|-- brain/              # Service 1: Python trading execution
|   |-- main.py         # Trading loop
|   |-- strategy.py     # AI-rewritable logic surface
|   |-- ensemble.py     # Quant, neural, and sentiment consensus math
|   `-- requirements.txt
|-- mirror/             # Service 2: Node.js market simulator
|   |-- server.js       # WebSocket and REST API
|   |-- engine.js       # Playback, pause, and skip controls
|   `-- data/           # Historical CSV/Parquet files, ignored by Git
|-- lab/                # Service 3: Python evolution engine
|   |-- evolver.py      # LLM interface and Git manager
|   |-- trainer.py      # Multi-asset, multi-pass historical training loop
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

Run three historical training passes across every CSV in a data directory:

```bash
python lab/trainer.py --data-dir data/fixtures --passes 3 --report run/latest_training_report.json
```

Generate a mock Lab rewrite candidate:

```bash
python lab/evolver.py --mistakes run/latest_training_report.json --strategy brain/strategy.py
```

Run the service stack target:

```bash
ollama pull deepseek-coder-v2
cp .env.template .env
docker-compose up --build
```

Current Mirror endpoints:

- `GET /health`
- `GET /status`
- `GET /candles`
- `GET /step?count=1`
- `GET /pause`
- `GET /resume`
- `GET /reset`

## Initial Documentation

- [Architecture](docs/ARCHITECTURE.md): service boundaries, data flow, and safe-rewrite model.
- [Engineering Playbook](docs/PLAYBOOK.md): environment, local debugging, config, database, and market data notes.
- [Evolution Workflow](docs/EVOLUTION_WORKFLOW.md): LLM strategy rewriting, sandbox tests, Git promotion, and rollback.
- [UX Storyboard](docs/UX_STORYBOARD.md): first-run, failure, evolution, and deployment scenes.
- [Implementation Backlog](docs/IMPLEMENTATION_BACKLOG.md): suggested build order for the first runnable version.

## Safety Position

This project should begin as a paper-trading and simulation system only. Live exchange execution should remain disabled until the Brain has explicit risk limits, audit logs, rollback controls, test coverage, out-of-sample validation, and manual approval gates. A strategy that performs well on historical replay is still not proven safe for live trading.

## Next Implementation Step

Replace the small committed fixture with a real five-year historical data adapter for multiple symbols, then wire Brain results into Postgres so the UI can read real prediction, mistake, and generation records.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Community Terms

Contributors and users are expected to be respectful, constructive, and safety-conscious. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Disclaimer

This project is experimental trading software. It is not financial advice, has no warranty, and must be used at your own risk. See [DISCLAIMER.md](DISCLAIMER.md).
