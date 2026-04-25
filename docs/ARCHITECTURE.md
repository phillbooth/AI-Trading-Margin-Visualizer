# Architecture

Neural-Twin is split into four services so strategy evolution can happen without tightly coupling market replay, execution logic, and the operator UI.

## Services

### Brain: Python Execution Service

The Brain owns trading decisions. It subscribes to live-like market ticks from the Mirror, calculates ensemble signals, records decisions, and emits paper-trade events.

Primary responsibilities:

- Maintain portfolio and position state.
- Calculate Quant, Neural, and Sentiment signals.
- Produce buy, sell, hold, or risk-reduction decisions.
- Log every decision with its full feature context.
- Expose a narrow strategy interface that the Lab is allowed to modify.
- Expose a read-only API for active strategy selection and promoted generation history.

The first AI-rewritable surface should be the active version file under `brain/versions/`. `brain/strategy.py` should remain a stable loader so the rest of the application keeps a fixed import path. Shared infrastructure, broker adapters, database clients, and state management should remain outside the rewrite surface.

### Mirror: Node.js Simulation Service

The Mirror turns historical data into a live stream. It should serve REST endpoints for replay control and WebSocket events for market ticks, portfolio updates, and simulation status.

Primary responsibilities:

- Load historical OHLCV files.
- Replay ticks or candles at configurable speed.
- Support terminal controls for pause, resume, and skip.
- Expose a deterministic replay mode for sandbox testing.
- Keep historical data handling separate from Brain strategy logic.

Node.js is a strong fit here because this service is I/O heavy and WebSocket oriented.

### Lab: Python Evolution Service

The Lab owns the strategy improvement loop. It reads mistake logs, asks an LLM for a constrained code change, validates the candidate in a sandbox, and promotes the new strategy only if it passes benchmarks.

Primary responsibilities:

- Build evolution prompts from mistake logs and current strategy code.
- Route LLM calls to Onyx, OpenAI, Claude, or another configured provider.
- Write candidate strategy files outside production paths.
- Run syntax checks, lint checks, and deterministic backtests.
- Commit approved strategy versions to Git.
- Reject or archive failed candidates.

### UI: Vue Command Center

The UI shows simulation state, Brain decisions, performance, mistakes, and evolution history.

Primary responsibilities:

- Display market replay and portfolio state.
- Highlight drawdowns, mistakes, and risk events.
- Show current strategy generation and Git history.
- Provide manual rollback and evolution controls.
- Keep the user aware of whether the system is simulating, testing, or deployed.

## Data Flow

```text
Historical data -> Mirror -> Brain -> Database
                         |       |         |
                         |       |         `-> Brain API -> UI
                         |       `-> Mistake logs -> Lab -> Candidate strategy
                         |                                |
                         `-------- Sandbox replay <--------`
```

## Safe Rewrite Boundary

The Lab must not rewrite the whole application. It should only generate candidate changes for a controlled strategy module or method. The first target is:

```text
brain/versions/strategy_gNNNN.py
```

`brain/strategy.py` should load the active generation selected by configuration rather than being overwritten directly.

Recommended guardrails:

- Keep broker credentials, database access, and filesystem operations unavailable from generated strategy code.
- Validate generated Python syntax before execution.
- Run candidates in a separate process with timeouts.
- Compare candidate performance against the current strategy on the same replay window.
- Include out-of-sample replay windows to reduce overfitting.
- Commit only after tests pass.
