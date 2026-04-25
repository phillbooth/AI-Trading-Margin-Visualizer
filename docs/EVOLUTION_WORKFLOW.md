# Evolution Workflow

The Lab is responsible for self-improvement, but it must treat generated code as untrusted until proven otherwise.

## Versioned Memory

Git acts as the memory of strategy evolution. Every approved strategy change should be traceable to a mistake, benchmark result, and commit.

A strategy generation should include:

- Git commit SHA.
- Parent generation.
- Prompt summary.
- Mistake log ID.
- Backtest window.
- Baseline metrics.
- Candidate metrics.
- Approval or rejection reason.

## Loop

1. Replay historical candles as if the next candle is unknown.
2. Ask the Brain for a next-candle prediction and paper decision.
3. Reveal the next historical candle and score the prediction as right, wrong, or flat.
4. Record prediction context, actual outcome, paper equity, drawdown, and any mistake.
5. Repeat across all configured assets and all configured passes.
6. At a checkpoint, decide whether there is enough evidence to attempt a rewrite.
7. Resolve the active strategy version and read that rewrite surface.
8. Ask the configured LLM for a constrained change.
9. Save the result as a candidate strategy.
10. Run syntax checks and static checks.
11. Run deterministic Mirror replays in the sandbox.
12. Compare candidate results against the current production strategy on the same windows plus out-of-sample windows.
13. Promote only if the candidate passes all thresholds.
14. Back up the current active strategy, write a new immutable strategy version, update the active strategy pointer, and write a promotion manifest.
15. Commit the approved change and notify the UI.

The system should learn from every prediction, but production code should not be rewritten after every candle. Per-candle self-modification makes the run unstable and encourages overfitting. The safe pattern is: record every outcome, batch evidence into checkpoints, generate a candidate, test it against baseline, then promote only if it improves risk-adjusted performance.

## Multi-Asset Training Sessions

A training session can run many symbols through many passes, such as ten shares with five years of candles each and three passes before stopping.

Session inputs:

- Historical data directory.
- Symbol list or CSV pattern.
- Pass count.
- Prediction horizon.
- Starting equity and risk limits.
- Current strategy generation.

Session outputs:

- Prediction count and accuracy.
- Average return error.
- Mistake count and mistake contexts.
- Paper equity and drawdown.
- Rewrite recommendation: hold current strategy or queue candidate.
- Contribution artifact for reproducible sharing when benchmark mode is used.

The first runnable implementation is `lab/trainer.py`.

Current v1 automation flow:

- `lab/trainer.py` writes the current training report before requesting a rewrite so the evolver always sees the current mistakes rather than a stale report.
- If the rewrite recommendation is `queue_candidate`, the trainer calls `lab/evolver.py` and then `lab/compare.py`.
- If the comparison verdict is `promote_candidate`, the trainer calls `lab/promote.py` unless you pass `--no-auto-promote`.
- `lab/continuous_runner.py` wraps that same trainer flow in a loop, with explicit `run/STOP`, `run/PAUSE`, `run/continuous.lock`, and `run/continuous_status.json` controls.
- `lab/trainer.py --benchmark <file>` applies a committed benchmark pack so contributors can run the same symbol set and thresholds.
- Promotion writes a new `brain/versions/strategy_gNNNN.py`, updates `config/active_strategy.json`, stores a backup snapshot of the previous active version, and writes a manifest under `run/promotions/` plus `run/latest_promotion_report.json`.
- After promotion, `lab/promote.py` attempts to upsert the promoted generation into Postgres. Database sync status is recorded in the promotion manifest and does not silently replace the file-system promotion result.
- `ACTIVE_STRATEGY_GENERATION` can override the configured active version for replay and debugging, but normal selection should come from `config/active_strategy.json`.
- The trainer writes a contribution manifest under `run/contributions/` by default so result summaries can be shared without sharing local secrets.

Continuous-loop operating rules:

- `reject_candidate` and `hold_for_review` are normal outcomes. They are not runner failures.
- The runner should stop only on an explicit stop file or after the configured consecutive failure limit is reached.
- Continuous mode still targets historical replay and paper evolution only. It is not permission for unattended live trading.

Current read path:

- The Brain API reads active generation and generation history from Postgres when it can.
- If Postgres is unavailable, the Brain API falls back to `config/active_strategy.json` and local version files so the UI can still render strategy history.

## Candidate Validation

Minimum checks for v1:

- Python parses successfully with `ast.parse`.
- Candidate exports the expected class or function.
- Candidate cannot import blocked modules.
- Candidate finishes within a strict timeout.
- Candidate does not reduce performance on the mistake replay.
- Candidate passes at least one out-of-sample replay window.
- Candidate respects max drawdown and trade frequency limits.

## Rollback

Rollback should be explicit and auditable. Prefer `git revert` for promoted strategy commits so history remains intact.

Before Git-backed rollback exists, the v1 promoter keeps local backup copies in `run/promotions/`. That is a recovery aid, not a substitute for real versioned rollback.

Manual rollback flow:

```text
UI rollback request -> Lab validates target generation -> Git revert -> Brain reload -> UI notification
```

Avoid destructive commands in automated rollback flows. The Lab should not run broad `git reset` commands in normal operation.

## LLM Provider Interface

Use a provider abstraction so `.env` controls the model without changing code.

```text
BaseLLM
|-- OnyxLLM
|-- OpenAILLM
|-- ClaudeLLM
`-- MockLLM for tests
```

The first implementation should support Onyx and a mock provider. Remote providers can be added after local sandboxing is reliable.

## Prompt Contract

The LLM should receive a narrow task and return code only.

Recommended constraints:

- Rewrite only the configured strategy class or method.
- Do not add filesystem, network, subprocess, or environment access.
- Preserve the public interface.
- Return valid Python code only.
- Keep decisions explainable through returned signal scores.

## Guardrails

| Risk | Guardrail |
| --- | --- |
| Hallucinated code | Parse, lint, import, and smoke-test before replay. |
| Overfitting | Include random out-of-sample windows. |
| Infinite loops | Execute candidates with process timeouts. |
| Unsafe imports | Block filesystem, subprocess, sockets, and environment reads. |
| API depletion | Limit attempts per day and per mistake. |
| Silent degradation | Store and compare baseline metrics for every candidate. |
| Live trading loss | Keep live execution disabled until paper trading, audit logs, manual approval, and broker risk limits exist. |
