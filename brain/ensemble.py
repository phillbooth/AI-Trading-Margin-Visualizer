from statistics import mean


def pct_change(current, previous):
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def clamp(value, low, high):
    return min(high, max(low, value))


def moving_average(values, window):
    if not values:
        return 0.0
    sample = values[-window:]
    return mean(sample)


def score_signals(candles):
    closes = [candle["close"] for candle in candles]
    volumes = [candle["volume"] for candle in candles]
    latest = closes[-1]
    previous = closes[-2] if len(closes) > 1 else latest
    fast_ma = moving_average(closes, 3)
    slow_ma = moving_average(closes, 8)
    momentum = pct_change(latest, closes[-5]) if len(closes) >= 5 else pct_change(latest, previous)
    volume_ratio = volumes[-1] / moving_average(volumes, 5) if len(volumes) >= 5 and moving_average(volumes, 5) else 1.0

    trend_score = 50 + clamp((fast_ma - slow_ma) / latest * 900, -28, 28)
    momentum_score = 50 + clamp(momentum * 9, -28, 28)
    participation_score = 50 + clamp((volume_ratio - 1) * 26, -18, 18)

    quant = clamp((trend_score * 0.55) + (momentum_score * 0.45), 0, 100)
    neural = clamp((trend_score * 0.35) + (momentum_score * 0.45) + (participation_score * 0.20), 0, 100)
    sentiment = clamp(52 + clamp(momentum * 4, -14, 14) + clamp((volume_ratio - 1) * 12, -10, 10), 0, 100)

    return {
        "quant": quant,
        "neural": neural,
        "sentiment": sentiment,
        "momentum_pct": momentum,
        "volume_ratio": volume_ratio,
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
    }
