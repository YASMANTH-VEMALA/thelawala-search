"""Loopback-only development/demo HTTP server; not a production deployment."""

from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STATIC = Path(__file__).resolve().parent / "static"


class SearchHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, engine, **kwargs):
        self.engine = engine
        super().__init__(*args, **kwargs)

    def send_content(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, status: int, value: dict) -> None:
        self.send_content(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/search":
            params = parse_qs(url.query, keep_blank_values=True)
            try:
                self.send_json(200, self.engine.search(params.get("q", [""])[0], include_unavailable=True))
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
        elif url.path == "/api/health":
            self.send_json(200, {"status": "ok", "products": len(self.engine.products),
                                 "as_of": self.engine.as_of.isoformat()})
        elif url.path in {"/", "/app.js", "/styles.css"}:
            name, content_type = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            }[url.path]
            self.send_content(200, (STATIC/name).read_bytes(), content_type)
        else:
            self.send_json(404, {"error": "Not found"})

    def log_message(self, format, *args):
        # Do not log customer query strings.
        pass


def serve(engine, port: int) -> None:
    handler = partial(SearchHandler, engine=engine)
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Thelawala Search: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nSearch server stopped.")
