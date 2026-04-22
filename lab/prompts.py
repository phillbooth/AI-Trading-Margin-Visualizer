SYSTEM_CONTRACT = """
You are rewriting one trading strategy surface only.
Return Python code only.
Preserve the public Strategy.predict(candles) interface.
Do not import filesystem, network, subprocess, socket, or environment modules.
Keep the strategy explainable through quant, neural, and sentiment scores.
"""


def build_rewrite_prompt(mistakes, strategy_source):
    mistake_summary = mistakes[:5]
    return {
        "contract": SYSTEM_CONTRACT.strip(),
        "mistakes": mistake_summary,
        "strategy_source": strategy_source,
        "task": "Improve next-candle direction prediction while reducing high-confidence wrong-direction mistakes.",
    }
