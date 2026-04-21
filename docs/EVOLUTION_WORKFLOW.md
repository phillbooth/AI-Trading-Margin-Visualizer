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

1. Detect a failure condition, such as drawdown, stop loss, missed risk signal, or degraded benchmark.
2. Create a mistake log with market context, indicators, sentiment, position state, and decision output.
3. Read the current strategy rewrite surface.
4. Ask the configured LLM for a constrained change.
5. Save the result as a candidate strategy.
6. Run syntax checks and static checks.
7. Run deterministic Mirror replays in the sandbox.
8. Compare candidate results against the current production strategy.
9. Promote only if the candidate passes all thresholds.
10. Commit the approved change and notify the UI.

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

Manual rollback flow:

```text
UI rollback request -> Lab validates target generation -> Git revert -> Brain reload -> UI notification
```

Avoid destructive commands in automated rollback flows. The Lab should not run broad `git reset` commands in normal operation.

## LLM Provider Interface

Use a provider abstraction so `.env` controls the model without changing code.

```text
BaseLLM
|-- OllamaLLM
|-- OpenAILLM
|-- ClaudeLLM
`-- MockLLM for tests
```

The first implementation should support Ollama and a mock provider. Remote providers can be added after local sandboxing is reliable.

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
