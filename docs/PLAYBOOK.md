# Engineering Playbook

This document captures the practical implementation rules for the first version of Neural-Twin.

## Local Runtime Targets

### Python

Use Python 3.11.x for the Brain and Lab services. It is a stable target for common data science and AI libraries.

Recommended packages:

- `psycopg[binary]` for Postgres reads and writes in the current Brain and Lab services.
- `requests` or `httpx` later, if you replace the current standard-library HTTP calls.
- `GitPython` for Git operations from the Lab.
- `pydantic` for typed config and event payload validation.
- `pytest` for unit and integration tests.
- `ccxt` later, only when exchange connectivity is introduced.

### Node.js

Use Node.js for the Mirror because it is a good fit for WebSocket streaming, terminal input, and non-blocking I/O.

Recommended packages:

- `ws` or Socket.IO for streaming events.
- `fastify` or Express for REST control endpoints.
- `csv-parse` for historical CSV ingestion.
- `dotenv` for local config loading.

### UI

Use Vue with Pinia for the command center. Keep it operational and information-dense rather than marketing oriented.

Recommended UI surfaces:

- Simulation status and controls.
- Market chart and current replay timestamp.
- Open positions and realized/unrealized PnL.
- Mistake log table.
- Strategy generation timeline.
- Candidate test results.

## Configuration

Commit `.env.template` and ignore `.env`.

Suggested template:

```bash
# Required for the default local Onyx setup
LLM_PROVIDER=onyx
ONYX_BASE_URL=http://localhost:3000
ONYX_API_MODE=app
ONYX_TOKEN=replace_me

# Optional overrides
# Onyx model and auth overrides
ONYX_MODEL=
ONYX_KEY=
ONYX_SECRET=
ONYX_DATABASE_ID=
ONYX_INSTALL_DIR=
ONYX_BOOT_TIMEOUT_SECONDS=60
LLM_MODEL=

# Local Docker Desktop boot helper for Onyx-on-Docker setups
DOCKER_DESKTOP_PATH=C:\Program Files\Docker\Docker\Docker Desktop.exe
DOCKER_BOOT_TIMEOUT_SECONDS=90

# Strategy selection override
# Leave blank in normal operation so config/active_strategy.json controls the active generation.
ACTIVE_STRATEGY_GENERATION=

# Runtime and replay settings
IS_PAPER_TRADING=true
BRAIN_API_PORT=3201
SIM_START_DATE=2021-01-01
SIM_SPEED=10x
HISTORICAL_DATA_PATH=data/fixtures/sample_stock_ohlcv.csv

# Demo broker
DEMO_BROKER_INITIAL_CASH=100
DEMO_BROKER_CURRENCY=USD
DEMO_BROKER_MAX_LEVERAGE=1
DEMO_BROKER_ALLOWED_SYMBOLS=AMZN,NVDA,GOOG
DEMO_BROKER_FEE_PCT=0.1
DEMO_BROKER_MIN_TRADE_INTERVAL_MS=300000
DEMO_BROKER_MAX_ORDER_PCT=10
DEMO_BROKER_MAX_DAILY_LOSS=5

# Broker mode and future real-broker adapter settings
BROKER_MODE=demo
BROKER_PROVIDER=
BROKER_ENVIRONMENT=demo
BROKER_API_BASE_URL=
BROKER_ACCOUNT_ID=
BROKER_API_KEY=
BROKER_API_SECRET=
ETORO_PUBLIC_API_KEY=
ETORO_USER_KEY=

# Live prediction assumptions
PREDICTION_ASSUMED_FEE_PCT=0.1

# Evolution limits
TRAINING_PASSES=3
MAX_EVOLUTION_ATTEMPTS_PER_DAY=3
MAX_DRAWDOWN_PCT=12
MAX_POSITION_SIZE_PCT=20
MAX_TRADES_PER_DAY=8

# Continuous training loop
CONTINUOUS_BENCHMARK=
CONTINUOUS_DATA_DIR=data/historical
CONTINUOUS_PATTERN=*.csv
CONTINUOUS_SYMBOLS=
CONTINUOUS_INTERVAL_SECONDS=3600
CONTINUOUS_PAUSE_POLL_SECONDS=30
CONTINUOUS_MAX_CONSECUTIVE_FAILURES=5
CONTINUOUS_IMPORT_SYMBOLS=
CONTINUOUS_IMPORT_YEARS=5
CONTINUOUS_IMPORT_OUT=data/historical

# Database overrides
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=neural_twin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

Current selection order for the active strategy is:

1. `ACTIVE_STRATEGY_GENERATION` if set
2. `config/active_strategy.json`
3. fallback `g0001`

Do not infer the active strategy from the latest modified file in `brain/versions/`.

Recommended `.gitignore` entries:

```text
.env
local_config.yaml
*.log
__pycache__/
.pytest_cache/
venv/
node_modules/
lab/candidates/
lab/mistake_logs/
data/historical/
pgdata/
.DS_Store
```

## Database Model

Use a polymorphic asset model: shared market data lives in common tables, while asset-specific vitals live in separate tables.

```sql
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32) UNIQUE NOT NULL,
    name TEXT,
    asset_type VARCHAR(24) NOT NULL,
    quote_currency VARCHAR(16),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE market_data (
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    time TIMESTAMPTZ NOT NULL,
    price_open DECIMAL,
    price_high DECIMAL,
    price_low DECIMAL,
    price_close DECIMAL NOT NULL,
    volume DECIMAL,
    source VARCHAR(64),
    PRIMARY KEY (asset_id, time)
);

CREATE TABLE stock_metrics (
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    time TIMESTAMPTZ NOT NULL,
    pe_ratio DECIMAL,
    eps DECIMAL,
    dividend_yield DECIMAL,
    split_factor DECIMAL,
    next_earnings_date DATE,
    PRIMARY KEY (asset_id, time)
);

CREATE TABLE crypto_metrics (
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    time TIMESTAMPTZ NOT NULL,
    market_cap DECIMAL,
    hashrate DECIMAL,
    exchange_inflow DECIMAL,
    exchange_outflow DECIMAL,
    on_chain_volume DECIMAL,
    PRIMARY KEY (asset_id, time)
);

CREATE TABLE commodity_metrics (
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    time TIMESTAMPTZ NOT NULL,
    warehouse_stocks DECIMAL,
    global_supply DECIMAL,
    inventory_level DECIMAL,
    production_cost DECIMAL,
    PRIMARY KEY (asset_id, time)
);
```

The current repo also persists promoted strategy generations into `strategy_generations`, including:

- `strategy_path`
- `comparison_report`
- `promotion_manifest`
- `is_active`
- `promoted_at`

The Brain API reads those rows for the UI timeline and falls back to `config/active_strategy.json` plus local version files when Postgres is unavailable.

## Market Data Sources

Use source adapters so the Brain never depends directly on a vendor API.

- Crypto: Binance public data, CoinGecko, exchange exports.
- Stocks: Alpaca, Yahoo Finance, Polygon.io, EODHD.
- Commodities: Nasdaq Data Link, EODHD, exchange or warehouse reports.
- Forex: OANDA, Polygon.io, broker exports.

Historical data should be normalized to the shared `market_data` table and stored as raw files under `data/historical/`, which is ignored by Git.

## Onyx + Ollama Runtime Note

If Onyx is running in Docker and Ollama is running on the Windows host, Onyx must use:

```text
http://host.docker.internal:11434
```

not:

```text
http://127.0.0.1:11434
```

After Docker starts or restarts, verify in `Admin -> Language Models` that:

- the Ollama provider still points to `http://host.docker.internal:11434`
- the expected Ollama model is visible
- the default text model is still set

## Postgres Migration Note

If you already have an existing Postgres data volume, changes in [db/init.sql](../db/init.sql) are not replayed automatically on container restart. Apply the new `ALTER TABLE` and `CREATE INDEX` statements manually or recreate the volume when you want a clean bootstrapped database.

## Graceful Shutdown

Each long-running service should handle `SIGINT` and `SIGTERM`.

On shutdown, save:

- Current simulation timestamp.
- Replay speed and pause state.
- Portfolio state.
- Open orders or simulated orders.
- Current strategy generation.
- Ensemble weights.

## Mirror Terminal Controls

The Mirror service should support local keyboard controls when running interactively:

```javascript
const readline = require('readline');
readline.emitKeypressEvents(process.stdin);

if (process.stdin.isTTY) {
  process.stdin.setRawMode(true);
}

process.stdin.on('keypress', (str, key) => {
  if (key.name === 'space') {
    isPaused = !isPaused;
    console.log(isPaused ? 'SIMULATION PAUSED' : 'SIMULATION RESUMED');
  }

  if (key.name === 'return') {
    skipDays(1);
    console.log('SKIPPED 24 HOURS');
  }

  if (key.ctrl && key.name === 'c') {
    shutdown();
  }
});
```
