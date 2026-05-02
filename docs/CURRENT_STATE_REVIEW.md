# Current State Review

This document describes what is actually implemented in the repository today, what is still prototype-only, and what should be refactored before more features are layered on top.

## Short Answer: does `ui/prototype/index.html` still matter?

Yes, but only as the current operator-facing prototype shell.

- It is the real entrypoint for the browser UI today.
- It is where the current static dashboard layout lives.
- It is not the final UI architecture promised by the docs. The repo still describes a future Vue command center, but the implemented UI is plain HTML, CSS, and JavaScript under `ui/prototype/`.

The root `index.html` is only a convenience redirect for opening the repo directly in a browser. It is not the main application shell in Docker, because the `ui` service serves `ui/prototype/` directly.

## What Is Actually Implemented

### Working today

- Static prototype UI under `ui/prototype/`
- Brain read-only API for strategy history and active generation
- Brain event APIs for recent decisions and mistakes
- Brain demo broker event API with Postgres-first + local fallback
- Lab training, candidate generation, comparison, promotion, and continuous loop
- Versioned strategy files under `brain/versions/`
- Historical stock importer under `data/import_stocks.py`
- Postgres schema with strategy-generation persistence and trainer/demo-broker event write paths wired

### Prototype or placeholder today

- UI replay/tick simulation is still local browser state
- Mirror is a local REST replay service, but it is not feeding the UI
- Brain Docker service currently runs the read API, not a continuously running decision engine
- Some UI views still fallback to local state when API/DB feeds are unavailable

## Architecture Drift

### 1. UI service description is ahead of reality

Docs still describe the UI as a Vue command center. The implemented UI is a static prototype:

- `ui/prototype/index.html`
- `ui/prototype/assets/app.js`
- `ui/prototype/assets/styles.css`

This is acceptable for now, but the docs must stop implying that the Vue app already exists.

### 2. UI mixes presentation and simulation logic

The current UI does three different jobs in one browser file:

- renders the operator dashboard
- simulates replay ticks locally
- invents local decisions and mistake events

Strategy timeline, decision log, mistake log, and broker notifications are now fed by Brain APIs when available. Replay ticks and replay-driven status are still generated in-browser.

### 3. Mirror exists, but the UI does not use it

The prototype labels state as `Mirror paused` and `Mirror streaming`, but those states are local browser state, not Mirror service state.

So today:

- Mirror is implemented as a basic REST service
- UI does not consume Mirror endpoints
- browser replay logic duplicates some of Mirror's conceptual role

This is the clearest redundant path in the repo.

### 4. Brain service is split between batch logic and API logic

There are currently two different Brain entry modes:

- `brain/main.py`: CLI historical backtest runner
- `brain/api_server.py`: read-only HTTP API

In Docker, the Brain service runs `api_server.py`, so the service named `brain` is not currently the live paper-trading execution loop described in the architecture docs.

That split is fine for now, but it should be documented explicitly so the repo does not imply that a persistent execution engine already exists.

### 5. Database schema is broader than current writes

The schema includes:

- `predictions`
- `decisions`
- `mistake_logs`
- `backtest_runs`
- `strategy_generations`

Only `strategy_generations` has meaningful end-to-end wiring today. The other tables are still mostly future-facing. That is not wrong, but the docs should describe them as planned persistence targets rather than implied live behavior.

### 6. Docker wiring favors fixtures more than real historical data

The stock importer writes real data to `data/historical/`, but:

- Mirror still mounts fixture data only
- default trainer examples often still use fixtures
- UI replay does not use imported historical data

This means the repo supports real historical training better than it supports real historical playback in the operator UI.

### 7. Root-level `package-lock.json` looks redundant

There is a root `package-lock.json` without a matching root `package.json`. Unless a root Node project is reintroduced, this file is noise and should be removed.

## Refactor Priorities

### Priority 1: separate UI from replay logic

Move replay state generation out of `ui/prototype/assets/app.js`.

Target shape:

- Mirror owns replay state
- Brain owns predictions and decisions
- UI renders fetched state

The UI should stop fabricating:

- replay ticks
- portfolio/status replay state

### Priority 2: make service names match actual runtime behavior

Document and then refactor toward:

- `brain/api_server.py` as the read API
- separate Brain execution loop process for historical/paper execution
- Mirror as the only replay source

Right now the service boundaries are described correctly in theory but only partially enforced in code.

### Priority 3: finish Postgres write paths

Persist real:

- predictions
- decisions
- mistake logs
- backtest runs

Once that is done, the UI can read real histories rather than local placeholders.

### Priority 4: choose one UI direction

There are two valid paths:

1. Keep the static prototype and continue evolving it into the real command center
2. Replace it with the promised Vue UI

What should not continue is pretending both are current. The repo should name one as active and one as future.

### Priority 5: remove small repo noise

Likely cleanup targets:

- root `package-lock.json` if no root Node app exists
- any docs that describe WebSocket/UI features as current when they are still planned

## Recommended Near-Term Architecture

The clean next shape is:

```text
Mirror -> replay state
Brain -> predictions, decisions, active strategy API
Lab -> train / evolve / compare / promote
Postgres -> run history and generation history
UI -> render API data only
```

That is the right direction because it removes duplicated simulation logic and turns the prototype into a proper frontend instead of a frontend-plus-mock-engine hybrid.
