import argparse
import json
import os
from pathlib import Path

from env_loader import load_repo_env
from prompts import build_rewrite_prompt
from providers import call_onyx_chat
from sandbox import validate_candidate_source, write_candidate


MOCK_CANDIDATE = '''from ensemble import clamp, score_signals


class Strategy:
    generation = 2
    name = "candidate_volatility_guard"

    def predict(self, candles):
        signals = score_signals(candles)
        consensus = (signals["quant"] + signals["neural"] + signals["sentiment"]) / 3
        volatility_guard = min(18, abs(signals["momentum_pct"]) * 4)
        adjusted = consensus - volatility_guard if consensus > 50 else consensus + volatility_guard
        expected_return_pct = clamp((adjusted - 50) / 18, -2.0, 2.0)
        confidence = clamp(abs(adjusted - 50) * 2.0, 0, 86)

        if expected_return_pct > 0.22 and confidence >= 22:
            direction = "UP"
        elif expected_return_pct < -0.22 and confidence >= 22:
            direction = "DOWN"
        else:
            direction = "FLAT"

        return {
            "direction": direction,
            "expected_return_pct": expected_return_pct,
            "confidence": confidence,
            "signals": signals,
            "reason": f"{self.name}: adjusted={adjusted:.2f}, confidence={confidence:.2f}",
        }
'''


def load_mistakes(report_path):
    path = Path(report_path)
    if not path.exists():
        return []
    report = json.loads(path.read_text(encoding="utf-8"))
    return report.get("mistakes", [])


def build_candidate_source(provider_name, prompt, args):
    if provider_name == "mock":
        return MOCK_CANDIDATE
    if provider_name == "onyx":
        return call_onyx_chat(
            prompt,
            base_url=args.onyx_base_url,
            model=args.onyx_model,
            token=args.onyx_token,
            database_id=args.onyx_database_id,
            api_key=args.onyx_key,
            api_secret=args.onyx_secret,
            mode=args.onyx_api_mode,
        )
    raise ValueError(f"Unsupported LLM provider: {provider_name}")


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Prepare a constrained strategy rewrite candidate.")
    parser.add_argument("--mistakes", default="run/latest_backtest.json")
    parser.add_argument("--strategy", default="brain/strategy.py")
    parser.add_argument("--candidate", default="lab/candidates/strategy_candidate.py")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "mock"))
    parser.add_argument("--onyx-base-url", default=os.getenv("ONYX_BASE_URL", ""))
    parser.add_argument("--onyx-model", default=os.getenv("ONYX_MODEL", os.getenv("LLM_MODEL", "")))
    parser.add_argument("--onyx-token", default=os.getenv("ONYX_TOKEN", ""))
    parser.add_argument("--onyx-database-id", default=os.getenv("ONYX_DATABASE_ID", ""))
    parser.add_argument("--onyx-key", default=os.getenv("ONYX_KEY", ""))
    parser.add_argument("--onyx-secret", default=os.getenv("ONYX_SECRET", ""))
    parser.add_argument("--onyx-api-mode", default=os.getenv("ONYX_API_MODE", "auto"))
    args = parser.parse_args()

    mistakes = load_mistakes(args.mistakes)
    strategy_source = Path(args.strategy).read_text(encoding="utf-8") if Path(args.strategy).exists() else ""
    prompt = build_rewrite_prompt(mistakes, strategy_source)
    candidate_source = build_candidate_source(args.provider, prompt, args)
    validate_candidate_source(candidate_source)
    candidate_path = write_candidate(args.candidate, candidate_source)

    result = {
        "provider": args.provider,
        "candidate": str(candidate_path),
        "mistake_count": len(mistakes),
        "prompt_task": prompt["task"],
        "status": "candidate_written",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
