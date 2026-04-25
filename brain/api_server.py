import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from db import fetch_active_strategy_record, fetch_strategy_history


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

        self.send_json(404, {"error": "Unknown Brain endpoint."})

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
