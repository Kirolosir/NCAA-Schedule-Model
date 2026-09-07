"""Receive copied public NCAA page data through a loopback-only import form."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs

DESTINATION = Path(__file__).resolve().parents[1] / "local_data/2025/stats_pages.json"
ORIGIN = "http://127.0.0.1:8879"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/import" or self.headers.get("Host") != "127.0.0.1:8879":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'<title>NCAA data import</title><h1>Local NCAA data import</h1><form method="post" action="/import"><label>Public page data<textarea name="data" id="data"></textarea></label><button>Save batch</button></form>')

    def do_POST(self):
        if (self.path != "/import" or self.headers.get("Origin") != ORIGIN
                or self.headers.get("Host") != "127.0.0.1:8879"):
            self.send_error(403)
            return
        size = int(self.headers.get("Content-Length", 0))
        if not 0 < size < 5_000_000:
            self.send_error(413)
            return
        try:
            rows = json.loads(parse_qs(self.rfile.read(size).decode())["data"][0])
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get("url", "").startswith("https://stats.ncaa.org/") for r in rows):
                raise ValueError("Expected public NCAA page records")
            saved = json.loads(DESTINATION.read_text()) if DESTINATION.exists() else {}
            saved.update({r["url"]: r for r in rows})
            DESTINATION.parent.mkdir(parents=True, exist_ok=True)
            DESTINATION.write_text(json.dumps(saved, ensure_ascii=False, indent=2)+"\n")
        except (ValueError, KeyError) as error:
            self.send_error(400, str(error))
            return
        self.send_response(303)
        self.send_header("Location", "/import")
        self.end_headers()


if __name__ == "__main__":
    print(f"Import form: {ORIGIN}/import", flush=True)
    HTTPServer(("127.0.0.1", 8879), Handler).serve_forever()
