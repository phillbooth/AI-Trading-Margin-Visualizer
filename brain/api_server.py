import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from demo_broker import broker_state, place_demo_order
from db import fetch_active_strategy_record, fetch_strategy_history
from live_watch import build_watchlist_predictions


PORT = int(os.getenv("BRAIN_API_PORT", "3201"))


class BrainApiHandler(BaseHTTPRequestHandler):
    def send_json(self, status_code, payload):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(200, {"ok": True, "service": "brain"})
            return

        if parsed.path == "/strategy/active":
            self.send_json(200, fetch_active_strategy_record())
            return

        if parsed.path == "/strategy/history":
            params = parse_qs(parsed.query)
            try:
                limit = max(1, min(50, int(params.get("limit", ["10"])[0])))
            except ValueError:
                limit = 10
            self.send_json(200, {"items": fetch_strategy_history(limit)})
            return

        if parsed.path == "/watchlist/predictions":
            params = parse_qs(parsed.query)
            symbols = params.get("symbols", [""])[0]
            period = params.get("period", ["6mo"])[0]
            interval = params.get("interval", ["1d"])[0]
            self.send_json(200, build_watchlist_predictions(symbols, period=period, interval=interval))
            return

        if parsed.path == "/broker/demo/state":
            self.send_json(200, broker_state())
            return

        self.send_json(404, {"error": "Unknown Brain endpoint."})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/broker/demo/order":
            self.send_json(404, {"error": "Unknown Brain endpoint."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        payload = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            if raw:
                payload = json.loads(raw.decode("utf-8"))

        try:
            result = place_demo_order(
                symbol=payload.get("symbol", ""),
                side=payload.get("side", ""),
                amount=payload.get("amount", 0),
                leverage=payload.get("leverage", 1),
            )
        except Exception as error:
            self.send_json(400, {"error": str(error)})
            return

        self.send_json(200, result)

    def log_message(self, format, *args):  # noqa: A003 - BaseHTTPRequestHandler API
        return


def main():
    server = HTTPServer(("0.0.0.0", PORT), BrainApiHandler)
    print(f"Brain API listening on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
