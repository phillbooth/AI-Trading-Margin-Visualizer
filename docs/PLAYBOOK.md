# Engineering Playbook

This document captures the practical implementation rules for the first version of Neural-Twin.

## Local Runtime Targets

### Python

Use Python 3.11.x for the Brain and Lab services. It is a stable target for common data science and AI libraries.

Recommended packages:

- `pandas` and `numpy` for vectorized market calculations.
- `requests` or `httpx` for service and LLM calls.
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
# LLM config
LLM_PROVIDER=onyx
ONYX_BASE_URL=http://localhost:3000
ONYX_API_MODE=app
ONYX_MODEL=
ONYX_TOKEN=replace_me
ONYX_KEY=
ONYX_SECRET=
LLM_MODEL=

# Exchange config
EXCHANGE_API_KEY=your_key_here
EXCHANGE_SECRET=your_secret_here
IS_PAPER_TRADING=true

# Simulation config
SIM_START_DATE=2021-01-01
SIM_SPEED=10x

# Database config
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=neural_twin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

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
