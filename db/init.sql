CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(32) UNIQUE NOT NULL,
    name TEXT,
    asset_type VARCHAR(24) NOT NULL,
    quote_currency VARCHAR(16),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_data (
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

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    strategy_generation INTEGER NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    horizon_candles INTEGER NOT NULL DEFAULT 1,
    predicted_direction VARCHAR(12) NOT NULL,
    predicted_return_pct DECIMAL NOT NULL,
    confidence DECIMAL NOT NULL,
    quant_score DECIMAL NOT NULL,
    neural_score DECIMAL NOT NULL,
    sentiment_score DECIMAL NOT NULL,
    actual_direction VARCHAR(12),
    actual_return_pct DECIMAL,
    was_correct BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT REFERENCES predictions(id),
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    decision VARCHAR(16) NOT NULL,
    reason TEXT,
    paper_position_size DECIMAL,
    paper_equity DECIMAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mistake_logs (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT REFERENCES predictions(id),
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    mistake_type VARCHAR(32) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    context JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_generations (
    id SERIAL PRIMARY KEY,
    generation INTEGER UNIQUE NOT NULL,
    git_commit_sha VARCHAR(64),
    parent_generation INTEGER,
    prompt_summary TEXT,
    validation_status VARCHAR(24) NOT NULL,
    baseline_metrics JSONB,
    candidate_metrics JSONB,
    approval_reason TEXT,
    strategy_path TEXT,
    candidate_snapshot_path TEXT,
    comparison_report JSONB,
    promotion_manifest JSONB,
    source_provider VARCHAR(32),
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    promoted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE strategy_generations
    ADD COLUMN IF NOT EXISTS strategy_path TEXT,
    ADD COLUMN IF NOT EXISTS candidate_snapshot_path TEXT,
    ADD COLUMN IF NOT EXISTS comparison_report JSONB,
    ADD COLUMN IF NOT EXISTS promotion_manifest JSONB,
    ADD COLUMN IF NOT EXISTS source_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS strategy_generations_one_active_idx
    ON strategy_generations (is_active)
    WHERE is_active;

CREATE INDEX IF NOT EXISTS strategy_generations_promoted_at_idx
    ON strategy_generations (promoted_at DESC NULLS LAST, created_at DESC);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    strategy_generation INTEGER NOT NULL,
    asset_id INTEGER REFERENCES assets(id),
    data_start TIMESTAMPTZ,
    data_end TIMESTAMPTZ,
    candle_count INTEGER NOT NULL,
    accuracy DECIMAL NOT NULL,
    avg_return_error DECIMAL NOT NULL,
    max_drawdown_pct DECIMAL NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS broker_events (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL,
    mode VARCHAR(24) NOT NULL DEFAULT 'demo',
    provider VARCHAR(32) NOT NULL DEFAULT 'local_demo',
    asset_id INTEGER REFERENCES assets(id),
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(16) NOT NULL,
    amount DECIMAL NOT NULL,
    units DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    leverage DECIMAL NOT NULL,
    estimated_fee DECIMAL NOT NULL DEFAULT 0,
    realized_pnl DECIMAL NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'accepted',
    reason TEXT,
    cash_after DECIMAL,
    currency VARCHAR(16),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS broker_events_event_time_idx
    ON broker_events (event_time DESC, id DESC);

CREATE INDEX IF NOT EXISTS broker_events_symbol_idx
    ON broker_events (symbol, event_time DESC);

INSERT INTO assets (symbol, name, asset_type, quote_currency)
VALUES ('SAMPLE', 'Sample Equity Fixture', 'STOCK', 'USD')
ON CONFLICT (symbol) DO NOTHING;
