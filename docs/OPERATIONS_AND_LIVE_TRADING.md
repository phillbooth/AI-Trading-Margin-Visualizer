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
- leverage cap: `1`
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

### What works now

The Brain now exposes a strictly local demo broker:

- `GET /broker/demo/state`
- `POST /broker/demo/order`

Current demo broker rules:

- paper only
- no shorting
- leverage capped at `1`
- optional symbol whitelist from `.env`
- local state file at `run/demo_broker_state.json`

Request body example:

```json
{
  "symbol": "AMZN",
  "side": "BUY",
  "amount": 25,
  "leverage": 1
}
```

### What the repo does not yet do

The repo still does **not** yet have:

- eToro broker adapter code
- demo/real broker account sync
- order reconciliation against a real third-party broker
- persistent broker audit trail in Postgres
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

1. Persist predictions, decisions, mistakes, and backtest runs to Postgres
2. Add a stock-watchlist benchmark and benchmark results view
3. Add live market watch mode with paper predictions only
4. Add broker adapter in demo mode
5. Add real-money broker mode only after the paper path is stable

## Sources

- eToro Developer Portal: https://api-portal.etoro.com/
- eToro Authentication: https://api-portal.etoro.com/getting-started/authentication
- eToro Open and close market orders: https://api-portal.etoro.com/guides/market-orders
- Alpha Vantage documentation: https://www.alphavantage.co/documentation/
- Polygon stocks docs: https://polygon.io/docs/rest/stocks/overview/
- FRED API overview: https://fred.stlouisfed.org/docs/api/fred/overview.html
