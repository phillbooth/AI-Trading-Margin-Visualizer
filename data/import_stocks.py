import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path


try:
    import yfinance as yf
except ImportError as error:  # pragma: no cover - depends on local environment
    raise SystemExit(
        "yfinance is required for data/import_stocks.py. "
        "Install it with: python -m pip install yfinance"
    ) from error


OUTPUT_COLUMNS = ["time", "symbol", "open", "high", "low", "close", "volume"]


def parse_symbols(value):
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def utc_market_open_timestamp(date_value):
    return f"{date_value.isoformat()}T14:30:00Z"


def fetch_history(symbol, years):
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=f"{years}y", interval="1d", auto_adjust=False, actions=False)
    if history.empty:
        raise ValueError(f"No history returned for {symbol}.")
    return history


def write_csv(symbol, history, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{symbol}.csv"

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        row_count = 0
        for timestamp, row in history.iterrows():
            trade_date = timestamp.date()
            open_value = row.get("Open")
            high_value = row.get("High")
            low_value = row.get("Low")
            close_value = row.get("Close")
            volume_value = row.get("Volume")

            values = [open_value, high_value, low_value, close_value, volume_value]
            if any(value is None for value in values):
                continue

            writer.writerow({
                "time": utc_market_open_timestamp(trade_date),
                "symbol": symbol,
                "open": f"{float(open_value):.6f}",
                "high": f"{float(high_value):.6f}",
                "low": f"{float(low_value):.6f}",
                "close": f"{float(close_value):.6f}",
                "volume": f"{float(volume_value):.0f}",
            })
            row_count += 1

    return path, row_count


def main():
    parser = argparse.ArgumentParser(description="Download historical stock OHLCV into fixture-compatible CSV files.")
    parser.add_argument("--symbols", required=True, help="Comma-separated stock symbols, e.g. AAPL,MSFT,NVDA")
    parser.add_argument("--years", type=int, default=5, help="Number of years of daily history to fetch")
    parser.add_argument("--out", default="data/historical", help="Output directory for CSV files")
    args = parser.parse_args()

    symbols = parse_symbols(args.symbols)
    if not symbols:
        raise SystemExit("No symbols supplied.")
    if args.years < 1:
        raise SystemExit("--years must be at least 1.")

    output_dir = Path(args.out)
    results = []

    for symbol in symbols:
        history = fetch_history(symbol, args.years)
        path, row_count = write_csv(symbol, history, output_dir)
        results.append({
            "symbol": symbol,
            "rows": row_count,
            "path": str(path),
        })

    print("Imported:")
    for item in results:
        print(f"- {item['symbol']}: {item['rows']} rows -> {item['path']}")


if __name__ == "__main__":
    main()
