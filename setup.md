# Setup

This file is the practical startup and verification checklist for this repository on the current local stack:

- Onyx at `http://localhost:3000`
- Ollama on the Windows host at `http://127.0.0.1:11434`
- Onyx running in Docker
- Repo scripts talking to Onyx, not directly to Ollama

## Daily Boot Checklist

This matches the current local machine behavior:

- Ollama normally comes up with Windows and is already running after boot
- Onyx does not auto-start and must be started manually

Daily startup sequence:

1. Confirm Ollama is alive:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
```

2. Start the Docker Desktop app before running any `docker` or `docker compose` commands.

Wait for Docker Desktop to finish booting. If the Docker app is not running yet, `docker ps` and other Docker commands will fail.

3. Start or confirm Onyx:

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
Invoke-WebRequest -UseBasicParsing http://localhost:3000/
```

Expected result:

- Onyx containers are up
- `http://localhost:3000` returns `200`

4. If Onyx was just started or restarted, re-check:

- `Admin -> Language Models`
- Ollama provider still points to `http://host.docker.internal:11434`
- expected model is still present
- default text model is still set

5. Then run repo services as needed:

```powershell
python brain\api_server.py
```

If you want the repo to try the local Onyx boot for you, set `ONYX_INSTALL_DIR` in `.env` and use:

```powershell
python brain\onyx_boot.py --ensure
```

On this machine, the configured local Onyx path is:

```text
C:\Users\desig\OneDrive\Documents\AI\onyx
```

Optional:

```powershell
python lab\continuous_runner.py --benchmark benchmarks\watchlist-us-stocks-v1.json --interval-seconds 3600
```

## 1. Start the local dependencies

Start Docker Desktop.

Make sure Ollama is installed and running on the Windows host.

If Ollama is not installed yet, install it first, then pull the model used in this setup:

```powershell
& 'C:\Users\<your-user>\AppData\Local\Programs\Ollama\ollama.exe' pull qwen2.5-coder:7b
```

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
ONYX_INSTALL_DIR=C:\Users\desig\OneDrive\Documents\AI\onyx
ONYX_BOOT_TIMEOUT_SECONDS=60
DOCKER_DESKTOP_PATH=C:\Program Files\Docker\Docker\Docker Desktop.exe
DOCKER_BOOT_TIMEOUT_SECONDS=90
ACTIVE_STRATEGY_GENERATION=
ONYX_MODEL=
BRAIN_API_PORT=3201
DEMO_BROKER_INITIAL_CASH=100
DEMO_BROKER_MAX_LEVERAGE=1
DEMO_BROKER_FEE_PCT=0.1
DEMO_BROKER_MIN_TRADE_INTERVAL_MS=300000
DEMO_BROKER_MAX_ORDER_PCT=10
DEMO_BROKER_MAX_DAILY_LOSS=5
BROKER_MODE=demo
BROKER_PROVIDER=
BROKER_ENVIRONMENT=demo
BROKER_API_BASE_URL=
BROKER_ACCOUNT_ID=
BROKER_API_KEY=
BROKER_API_SECRET=
ETORO_PUBLIC_API_KEY=
ETORO_USER_KEY=
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=neural_twin
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

`DEMO_BROKER_MAX_LEVERAGE` defaults to `1`. If you deliberately want higher-risk testing, raise it to `5` or `10`. The current demo broker enforces a hard ceiling of `10` even if a higher value is configured.

`DEMO_BROKER_MIN_TRADE_INTERVAL_MS` is part of the trading risk model, not just a convenience throttle. The Brain live-watch output now includes cooldown-aware execution guardrails, so a strategy may still predict `BUY` while execution is told to `WAIT_COOLDOWN` until the interval expires.

`ONYX_INSTALL_DIR` lets the repo find your local Onyx Docker Compose setup. The helper searches that folder and common subfolders like `deployment\docker_compose`, then runs `docker compose up -d` there. If Docker Desktop is not running yet, the helper first tries to start it using `DOCKER_DESKTOP_PATH`.

Broker credential guidance:

- keep `BROKER_MODE=demo` unless a real broker adapter has been implemented and explicitly enabled
- keep live broker keys only in your local `.env`
- do not reuse the demo broker settings block for real credentials
- if you later use eToro, store its keys in `ETORO_PUBLIC_API_KEY` and `ETORO_USER_KEY`
- these credentials are placeholders today; the repo does not yet place live broker orders

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

You can check or bootstrap the local Onyx stack directly:

```powershell
python brain\onyx_boot.py
python brain\onyx_boot.py --ensure
```

Or through the Brain API after `python brain\api_server.py` is running:

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:3201/ops/onyx/status"
Invoke-WebRequest -UseBasicParsing -Method POST "http://localhost:3201/ops/onyx/bootstrap"
```

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

For live-watch and demo trading checks, also verify:

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:3201/watchlist/predictions?symbols=AMZN,NVDA,GOOG"
Invoke-WebRequest -UseBasicParsing "http://localhost:3201/broker/demo/state"
```

In the live-watch response, check `execution_guardrails.cooldown`. If `can_trade_now` is `false`, the app should treat the current signal as blocked by the configured interval.

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

Common local startup failures:

- If `docker ps` returns an error mentioning `dockerDesktopLinuxEngine` or `The system cannot find the file specified`, Docker Desktop is not running yet. Start Docker Desktop first, wait for it to finish booting, then run `docker ps` again.
- If `Invoke-WebRequest http://localhost:3000/` says `Unable to connect to the remote server`, Onyx is not running yet. In this setup, that usually means Docker Desktop was not running or the Onyx containers were not started.
- Do not try to diagnose Onyx first when `docker ps` is already failing. The first fix is to start the Docker Desktop app.

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
