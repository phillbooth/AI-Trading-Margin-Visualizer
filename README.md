# Neural-Twin: Autonomous Self-Evolving Quant

Neural-Twin is a four-service framework for simulating, executing, and evolving trading strategies across crypto, stocks, commodities, and other asset classes. The system is designed around a controlled simulation loop: a Mirror service replays historical markets as if they are live, a Brain service makes paper-trading decisions, a Lab service proposes strategy improvements, and a UI service shows the current state of the system.

This repository currently starts as the project documentation pack. The first implementation pass should create the service folders, configuration files, database schema, and minimal runnable containers described here.

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
|   |-- sandbox.py      # Isolated test runner
|   `-- prompts.py      # Code-generation prompts and policies
|-- ui/                 # Service 4: Vue command center
|   |-- src/            # Vue components and Pinia stores
|   `-- tailwind.config.js
|-- db/                 # Persistent storage setup
|   `-- init.sql        # Multi-asset schema
`-- docs/               # Project design and implementation notes
```

## Quick Start Target

The future local development flow should look like this:

```bash
ollama pull deepseek-coder-v2
cp .env.template .env
docker-compose up --build
```

Expected controls once the Mirror service exists:

- Press `Space` in the Mirror terminal to pause or resume simulation playback.
- Press `Enter` in the Mirror terminal to skip forward one simulation day.
- Use `Ctrl+C` or `docker stop` for graceful shutdown and state persistence.

## Initial Documentation

- [Architecture](docs/ARCHITECTURE.md): service boundaries, data flow, and safe-rewrite model.
- [Engineering Playbook](docs/PLAYBOOK.md): environment, local debugging, config, database, and market data notes.
- [Evolution Workflow](docs/EVOLUTION_WORKFLOW.md): LLM strategy rewriting, sandbox tests, Git promotion, and rollback.
- [UX Storyboard](docs/UX_STORYBOARD.md): first-run, failure, evolution, and deployment scenes.
- [Implementation Backlog](docs/IMPLEMENTATION_BACKLOG.md): suggested build order for the first runnable version.

## Safety Position

This project should begin as a paper-trading and simulation system only. Live exchange execution should remain disabled until the Brain has explicit risk limits, audit logs, rollback controls, test coverage, and manual approval gates.

## Next Implementation Step

Create the repository scaffolding and infrastructure files:

- `.gitignore`
- `.env.template`
- `docker-compose.yml`
- `db/init.sql`
- minimal `brain/`, `mirror/`, `lab/`, and `ui/` service skeletons

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Community Terms

Contributors and users are expected to be respectful, constructive, and safety-conscious. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Disclaimer

This project is experimental trading software. It is not financial advice, has no warranty, and must be used at your own risk. See [DISCLAIMER.md](DISCLAIMER.md).

