# Operations And Live Trading

This document separates what the repo can do now from what still needs to be built for live prediction and real-money trading.

## 1. Continuous training and historical stock analysis

### What works now

The repo can already:

- import historical stock OHLCV into CSV files
- run repeated training passes
- generate candidate strategy rewrites
- compare candidates against the baseline
- promote only if the candidate passes the gate
- run continuously until stopped

### Historical import

Import stock history:

```powershell
python data\import_stocks.py --symbols AAPL,MSFT,NVDA,AMZN,GOOGL --years 5 --out data\historical
```

For the current stock subset from your watchlist, this importer was verified to work with:

```powershell
python data\import_stocks.py --symbols MRVL,NVDA,INTC,HSBC,AMC,QCOM,GOOG,AMD,AMZN,L,COHR,BBAI --years 5 --out data\historical
```

### Benchmark-driven training

Run the shared large-cap benchmark:

```powershell
python lab\trainer.py --benchmark benchmarks\us-large-cap-daily-v1.json
```

Run the stock subset from your own watchlist:

```powershell
python lab\trainer.py --benchmark benchmarks\watchlist-us-stocks-v1.json
```

### Continuous training

Run the historical loop continuously:

```powershell
python lab\continuous_runner.py --benchmark benchmarks\watchlist-us-stocks-v1.json --interval-seconds 3600
```

Controls:

- `run\STOP`: stop cleanly
- `run\PAUSE`: pause without exiting
- `run\continuous_status.json`: current state and last cycle summary

### What the current output means

A result like:

- `candidate_written`
- `candidate_verdict: reject_candidate`
- `promotion_status: skipped`

is healthy. It means:

1. the model rewrite path worked
2. the comparison gate ran
3. the candidate was blocked from promotion because it worsened the strategy

That is the correct behavior.

## 2. Live stock market watch and live prediction

### What works now

The Brain now exposes a basic live-watch endpoint for delayed stock snapshots and paper predictions:

- `GET /watchlist/predictions?symbols=AMZN,NVDA,GOOG`

This endpoint:

- fetches recent daily candles from Yahoo Finance
- runs the active strategy against that recent history
- returns a current paper prediction and paper decision per symbol
- returns a target exit price based on the model's expected move
- estimates net expected return after assumed fees

### What is not built yet

The app still does not run a full persistent live-market prediction loop.

Current reality:

- the strategy timeline is API-backed
- the browser replay tape is still local simulated UI state
- Mirror is not yet connected to a live market feed
- the new watchlist endpoint is read-only and request-driven, not a streaming service

### What needs to be built

To watch live stocks and predict with the app, add these pieces:

1. **Live market data adapter**
   - one service for current quotes, trades, bars, and market status
   - store live ticks or bars in Postgres

2. **Brain live mode**
   - subscribe to the live data adapter
   - compute prediction features on each new bar
   - emit predictions and paper decisions
   - persist predictions and decisions

3. **UI live screens**
   - current quote
   - live prediction
   - confidence
   - paper position
   - recent decisions and mistakes

4. **Paper trading first**
   - before any real broker execution

### Recommended live path

Use this sequence:

1. historical training
2. live market watch + paper predictions
3. live paper trading
4. demo broker execution
5. tiny real-money execution with strict limits

Do not skip straight from historical replay to live money.

## 3. Real transactions

### New requirement

Real trading should be treated as a separate operating mode with a dedicated broker adapter and stricter controls than the current repo has today.

### eToro API

As of April 25, 2026, eToro has a public API and developer portal. Their official docs say:

- the API supports market data, portfolio data, and trading functions
- access requires a verified eToro account
- authentication uses a Public API Key plus a User Key
- keys are created in `Settings -> Trading -> API Key Management`
- each key is created for either `Demo` or `Real`
- permissions can be `Read` or `Write`

The order flow in the eToro docs is:

1. resolve the `instrumentId`
2. place an open order by amount or units
3. set leverage, stop-loss, and take-profit in the order request
4. close by `positionId`

For this project, the correct way to introduce real trading is:

1. build an `etoro_adapter.py`
2. support `demo` first
3. support `read-only` checks
4. then support `write`
5. enforce local risk limits before any order is sent

### Your example: £100, x1 leverage, micro-trading

That is a sensible starting constraint set for a future real-trading mode:

- broker budget cap: `100 GBP`
- leverage cap: `1` by default
- max single position: small fraction of total cash
- allowed instruments: explicit whitelist only
- default environment: `demo`
- real environment: opt-in only

### Minimum real-trading safeguards

Before live execution exists, require:

- explicit broker mode: `demo` or `real`
- instrument whitelist
- max capital allocation
- max open positions
- max daily loss
- max order size
- forced stop-loss
- cooldown between trades
- human-readable audit log
- kill switch

### Environment structure for future live credentials

Do not overload the current demo broker settings with real broker secrets.

Use a separate section in local `.env`:

```bash
BROKER_MODE=demo
BROKER_PROVIDER=
BROKER_ENVIRONMENT=demo
BROKER_API_BASE_URL=
BROKER_ACCOUNT_ID=
BROKER_API_KEY=
BROKER_API_SECRET=
ETORO_PUBLIC_API_KEY=
ETORO_USER_KEY=
```

Guidance:

- keep `BROKER_MODE=demo` until a real adapter is implemented and validated
- keep demo cash/risk settings under the `DEMO_BROKER_*` block
- keep real broker secrets separate so there is no ambiguity about execution mode
- store live credentials only in local `.env`, never in `.env.template` with real values and never in Git
- for eToro specifically, the future adapter should read `ETORO_PUBLIC_API_KEY` and `ETORO_USER_KEY`

### What works now

The Brain now exposes a strictly local demo broker:

- `GET /broker/demo/state`
- `POST /broker/demo/order`

Current demo broker rules:

- paper only
- no shorting
- leverage defaults to `1`
- leverage can be raised deliberately to `5` or `10`
- hard leverage ceiling enforced at `10`
- fee-aware cash accounting
- trade cooldown enforced in milliseconds
- max order size cap enforced as a percentage of available cash
- max realized daily loss cap enforced before new trades
- optional symbol whitelist from `.env`
- local state file at `run/demo_broker_state.json`
- raw order history kept in local broker state for now

The trade interval is also reflected in the prediction layer now. Live-watch responses include `execution_guardrails`, which can convert an otherwise valid `BUY` or `SELL` signal into `WAIT_COOLDOWN` when the minimum interval between trades has not elapsed.

Request body example:

```json
{
  "symbol": "AMZN",
  "side": "BUY",
  "amount": 25,
  "leverage": 1,
  "take_profit_pct": 1.5
}
```

Conservative default trade-rate limit:

- `DEMO_BROKER_MIN_TRADE_INTERVAL_MS=300000`

That is one trade every 5 minutes. It is a sensible conservative default for early live-style testing because it reduces overtrading and makes review easier.

Operationally, treat this interval as part of the risk equation:

- it reduces rapid flip-trading on noisy signals
- it forces a minimum pause between executions
- it should be reviewed alongside leverage, fees, max order size, and max daily loss
- it is reported back through the Brain API so the UI can show when execution is blocked by cooldown rather than market logic

Other conservative defaults now supported:

- `DEMO_BROKER_MAX_ORDER_PCT=10`
- `DEMO_BROKER_MAX_DAILY_LOSS=5`
- `DEMO_BROKER_FEE_PCT=0.1`

For a small starter account, those defaults mean:

- a single new buy cannot exceed 10% of current cash
- once realized loss for the day reaches 5 units of account currency, new trades are blocked
- every buy and sell includes fee-aware cash handling

### Notification log requirement

Before this moves beyond a local demo broker, the app needs a dedicated broker notification log.

It should record events like:

- bought `AMZN` for `10.00 USD`
- sold `AMZN` at `267.00 USD`
- realized profit after fees
- blocked trade because cooldown is active
- blocked trade because max order size or daily loss cap was hit

That log should exist in two forms:

1. operator-facing notification items for the UI
2. persistent broker events for audit and debugging

Recommended event fields:

- timestamp
- mode: `demo` or `live`
- symbol
- side
- amount
- units
- price
- fees
- realized PnL
- cash after
- event type
- short human-readable message

### What the repo does not yet do

The repo still does **not** yet have:

- eToro broker adapter code
- demo/real broker account sync
- order reconciliation against a real third-party broker
- persistent broker audit trail and notification log in Postgres
- production-grade live risk management

So the answer is: **yes, eToro is now a plausible broker integration target, but this repo currently implements only a local demo broker path and should stay there until the real adapter is built.**

## 4. Your watchlist symbols

### Stock-first benchmark ready now

The current importer was verified for this stock subset:

- `MRVL`
- `NVDA`
- `INTC`
- `HSBC`
- `AMC`
- `QCOM`
- `GOOG`
- `AMD`
- `AMZN`
- `L`
- `COHR`
- `BBAI`

Use:

```powershell
python data\import_stocks.py --symbols MRVL,NVDA,INTC,HSBC,AMC,QCOM,GOOG,AMD,AMZN,L,COHR,BBAI --years 5 --out data\historical
python lab\trainer.py --benchmark benchmarks\watchlist-us-stocks-v1.json
```

### Symbols that need mapping work

Some symbols in your list are not ready to use as-is with the current historical importer because they are exchange-specific or broker-specific aliases:

- `BT.L`
- `NESN.ZU`
- `SMSN.L`
- `OIL`
- `GOLD`
- `BTC`
- `MIOTA`

Those need a symbol-normalization layer for the selected data source. For example, Yahoo Finance, eToro, and other providers may all use different symbols for the same instrument.

For now, keep the active benchmark stock-only until symbol normalization is built.

## 5. Can news and politics help predictions?

Yes. This is one of the highest-value upgrades after price-only replay.

### Historical prediction improvement

For historical backtests, the important rule is:

- only use information that would have been available at that timestamp

That means storing timestamped exogenous features such as:

- company news
- earnings releases
- economic releases
- central bank statements
- inflation and interest-rate series
- broad market regime features

### Live prediction improvement

For live mode, add:

- real-time news feed
- ticker-tagged article ingestion
- event scoring
- macro calendar
- earnings calendar
- sentiment features

### Good data sources for this layer

Official docs currently show:

- **Alpha Vantage**: historical and live market news/sentiment API
- **Polygon**: stock news and stock market data APIs
- **FRED**: macroeconomic time series API

That gives a clean split:

- market prices/bars
- company news
- macroeconomic context

### Recommended implementation order

1. persist predictions, decisions, mistakes, and backtest runs
2. add live market data mode
3. add news ingestion
4. add macro series ingestion
5. add timestamp-safe historical event features
6. retrain and compare again

## 6. Recommended next build order

1. Persist predictions, decisions, mistakes, backtest runs, and broker notification events to Postgres
2. Add a stock-watchlist benchmark and benchmark results view
3. Add live market watch mode with paper predictions only
4. Add UI notification log for demo/live broker events
5. Add broker adapter in demo mode
6. Add real-money broker mode only after the paper path is stable

## Sources

- eToro Developer Portal: https://api-portal.etoro.com/
- eToro Authentication: https://api-portal.etoro.com/getting-started/authentication
- eToro Open and close market orders: https://api-portal.etoro.com/guides/market-orders
- Alpha Vantage documentation: https://www.alphavantage.co/documentation/
- Polygon stocks docs: https://polygon.io/docs/rest/stocks/overview/
- FRED API overview: https://fred.stlouisfed.org/docs/api/fred/overview.html
