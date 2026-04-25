# Setup

This file is the practical startup and verification checklist for this repository on the current local stack:

- Onyx at `http://localhost:3000`
- Ollama on the Windows host at `http://127.0.0.1:11434`
- Onyx running in Docker
- Repo scripts talking to Onyx, not directly to Ollama

## 1. Start the local dependencies

Start Docker Desktop.

Make sure Ollama is running on the Windows host.

If Onyx is already installed in Docker, confirm it is up:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Invoke-WebRequest -UseBasicParsing http://localhost:3000/
```

Expected result:

- `onyx-nginx-1`, `onyx-web_server-1`, `onyx-api_server-1`, and `onyx-relational_db-1` are up
- `http://localhost:3000` returns `200`

## 2. Check Ollama directly on the host

Verify that Ollama is reachable and the expected model exists:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
ollama run qwen2.5-coder:7b "say hello"
```

Expected result:

- `/api/tags` returns `200`
- the model list includes `qwen2.5-coder:7b`
- `ollama run` returns a normal response

## 3. Check Onyx model configuration

In Onyx:

1. Open `Admin -> Language Models`
2. Confirm the Ollama provider exists
3. Confirm the Ollama URL is:

```text
http://host.docker.internal:11434
```

4. Confirm the model is visible
5. Confirm the default text model is set

If Onyx is running in Docker, do not use `http://127.0.0.1:11434` inside the Onyx provider config. That points back to the container, not the Windows host.

## 4. Check the repo `.env`

The repo `.env` should contain normal single-line `KEY=value` entries. The required section for this local stack is:

```bash
LLM_PROVIDER=onyx
ONYX_BASE_URL=http://localhost:3000
ONYX_API_MODE=app
ONYX_TOKEN=your_service_account_key
```

Typical local optional values:

```bash
ACTIVE_STRATEGY_GENERATION=
ONYX_MODEL=
BRAIN_API_PORT=3201
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=neural_twin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

To verify that the repo loads the expected values:

```powershell
@'
from lab.env_loader import load_repo_env
import os
load_repo_env()
for key in ["LLM_PROVIDER", "ONYX_BASE_URL", "ONYX_API_MODE", "ONYX_MODEL", "ACTIVE_STRATEGY_GENERATION"]:
    print(f"{key}={os.getenv(key)!r}")
'@ | python -
```

Expected result:

- `LLM_PROVIDER='onyx'`
- `ONYX_BASE_URL='http://localhost:3000'`
- `ONYX_API_MODE='app'`
- `ONYX_MODEL=''` is fine if Onyx has a default model configured
- `ACTIVE_STRATEGY_GENERATION=''` is fine in normal operation

## 5. Verify the repo -> Onyx -> Ollama path

From the repo root:

```powershell
python lab\evolver.py --provider onyx --mistakes run\latest_training_report.json --strategy brain\strategy.py
```

Expected result:

```json
{
  "provider": "onyx",
  "candidate": "lab\\candidates\\strategy_candidate.py",
  "status": "candidate_written"
}
```

That confirms:

```text
repo script -> Onyx -> Ollama -> candidate file written
```

## 6. Verify the training loop

Run:

```powershell
python lab\trainer.py --data-dir data\fixtures --passes 3 --report run\latest_training_report.json
```

Or use a committed benchmark pack:

```powershell
python lab\trainer.py --benchmark benchmarks\us-large-cap-daily-v1.json
```

Expected result:

- the run completes
- a training report is written under `run/`
- if evolution is triggered, the trainer calls the evolver and comparison steps automatically
- a contribution artifact is written under `run\contributions\` by default

If this fails while `lab\evolver.py` works, the first thing to check is whether `.env` has a malformed blank `LLM_PROVIDER` or `ONYX_API_MODE`.

## 7. Start the Brain API for the UI timeline

Run:

```powershell
python brain\api_server.py
```

Then verify:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:3201/strategy/active
Invoke-WebRequest -UseBasicParsing "http://localhost:3201/strategy/history?limit=8"
Invoke-WebRequest -UseBasicParsing "http://localhost:3201/watchlist/predictions?symbols=AMZN,NVDA,GOOG"
Invoke-WebRequest -UseBasicParsing http://localhost:3201/broker/demo/state
```

The prototype timeline reads these endpoints when available and falls back to local version files when the database is unavailable.

## 8. If something breaks

Check these in order:

1. `http://localhost:3000` still loads
2. Ollama still responds at `http://127.0.0.1:11434/api/tags`
3. Onyx still points to `http://host.docker.internal:11434`
4. the Onyx default text model is still set
5. the repo `.env` still contains valid single-line `KEY=value` entries

## 9. Next repo task

The next concrete build step is:

- add a real stock data adapter
- fetch five years of OHLCV into `data/historical/`
- persist predictions, decisions, mistake logs, and backtest runs to Postgres
- replace the remaining local replay-only UI event history with database-backed records

## 10. Historical stock import

The repository now includes a stock importer:

```powershell
python data\import_stocks.py --symbols AAPL,MSFT,NVDA,AMZN,GOOGL --years 5 --out data\historical
```

You can import any stock symbols you want by changing the comma-separated `--symbols` value. Examples:

```powershell
python data\import_stocks.py --symbols TSLA,META,NFLX --years 5 --out data\historical
python data\import_stocks.py --symbols JPM,GS,BAC --years 10 --out data\historical
python data\import_stocks.py --symbols KO,PEP,PG,WMT --years 3 --out data\historical
```

The importer writes one CSV per symbol into the chosen output directory, for example:

- `data\historical\AAPL.csv`
- `data\historical\MSFT.csv`
- `data\historical\TSLA.csv`

If the dependency is missing:

```powershell
python -m pip install yfinance
```

After import, train against the real historical directory:

```powershell
python lab\trainer.py --data-dir data\historical --passes 3 --report run\historical_training_report.json
```

## 11. Continuous historical loop

Run the local continuous loop:

```powershell
python lab\continuous_runner.py --data-dir data\historical --passes 3 --interval-seconds 3600
```

Or use a benchmark pack:

```powershell
python lab\continuous_runner.py --benchmark benchmarks\us-large-cap-daily-v1.json --interval-seconds 3600
```

Optional data refresh before each cycle:

```powershell
python lab\continuous_runner.py --passes 3 --interval-seconds 3600 --import-symbols AAPL,MSFT,NVDA,AMZN,GOOGL --import-years 5
```

Control files:

- `run\continuous.lock`: prevents overlapping runners
- `run\continuous_status.json`: current state, last summary, and next wake-up time
- `run\STOP`: stop cleanly
- `run\PAUSE`: pause without exiting; remove it to resume

What to expect:

- The runner calls `lab\trainer.py`, so compare and promotion gates remain unchanged.
- `reject_candidate` is a valid result. It means the candidate failed the comparison gate and was not promoted.
- The runner stops after `CONTINUOUS_MAX_CONSECUTIVE_FAILURES` failed cycles unless you change that limit in `.env`.

## 12. Benchmark packs and shareable results

The repo now supports committed benchmark definitions under `benchmarks\`.

Current example:

- `benchmarks\us-large-cap-daily-v1.json`

These files define:

- symbol set
- data directory
- pass count
- window
- equity
- thresholds

The goal is reproducible community evaluation. People can run the same benchmark and share the resulting contribution artifact from `run\contributions\` without sharing `.env` credentials.
