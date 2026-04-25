from ensemble import clamp, score_signals


class Strategy:
    generation = 1
    name = "baseline_trend_consensus"

    def predict(self, candles):
        signals = score_signals(candles)
        consensus = (signals["quant"] + signals["neural"] + signals["sentiment"]) / 3
        expected_return_pct = clamp((consensus - 50) / 16, -2.5, 2.5)
        confidence = clamp(abs(consensus - 50) * 2.4, 0, 100)

        if expected_return_pct > 0.18 and confidence >= 18:
            direction = "UP"
        elif expected_return_pct < -0.18 and confidence >= 18:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "direction": direction,
            "expected_return_pct": expected_return_pct,
            "confidence": confidence,
            "signals": signals,
            "reason": f"{self.name}: consensus={consensus:.2f}, confidence={confidence:.2f}",
        }
