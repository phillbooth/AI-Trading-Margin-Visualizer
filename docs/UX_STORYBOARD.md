# UX Storyboard

The UI should present the system as an operational command center. The user should always know whether the app is replaying history, trading on paper, testing a candidate, or deploying a new strategy.

## Scene 1: First Run

The user starts the app. The UI opens with an empty or flat equity line, a paused simulation clock, and no open positions.

The user presses `Space` in the Mirror terminal. The Mirror starts streaming Bitcoin data from the configured start date. The Brain receives its first candle, calculates ensemble scores, and emits a paper decision.

Expected UI state:

- Simulation clock starts moving.
- Market chart begins drawing candles or ticks.
- Brain status changes to active.
- Decision log receives the first hold, buy, or sell event.

## Scene 2: Failure

The replay reaches a flash crash or sharp drawdown. The Brain loses theoretical capital or violates a risk threshold.

Expected UI state:

- PnL and drawdown indicators move into warning or danger states.
- The mistake log records RSI, volatility, sentiment, price action, position state, and the decision taken.
- The event appears in the mistake table with a replay button.

## Scene 3: Evolution

The Lab wakes up after a qualifying mistake. It sends the mistake summary and current strategy rewrite surface to the configured LLM.

The LLM proposes a bounded strategy change, such as adding a volatility filter. The Lab tests the candidate by replaying the mistake window plus out-of-sample data.

Expected UI state:

- Lab status changes to testing candidate.
- Candidate metrics appear beside baseline metrics.
- The user can see whether the candidate reduced loss, improved profit, or failed validation.

## Scene 4: Commitment

The candidate passes validation. The Lab commits the strategy change and notifies the Brain.

Expected UI state:

- Strategy generation increments.
- Timeline receives a new Git commit node.
- Notification appears: `New strategy deployed`.
- Brain reloads the strategy and continues simulation.

## Scene 5: Manual Rollback

The user decides a generation is too aggressive or performs poorly on later replay.

Expected UI state:

- User selects a prior strategy generation.
- UI shows baseline metrics and commit details.
- User confirms rollback.
- Lab reverts the relevant commit and Brain reloads.

## Theatre Mode

Theatre Mode is a focused replay for mistakes.

Flow:

1. Select a mistake.
2. Replay the original strategy failure.
3. Run or select an evolved strategy.
4. Replay the same market segment.
5. Compare original and evolved outcomes side by side.

This mode should make the evolution process inspectable rather than mysterious.
