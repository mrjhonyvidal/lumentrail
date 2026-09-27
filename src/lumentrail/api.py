"""Read-only JSON API for a versioned demo index."""

from __future__ import annotations

import hmac
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .embedding import make_embedder
from .retrieval import search


def serve(database_path: Path, host: str, port: int, embedding: str) -> None:
    token = os.environ.get("LUMENTRAIL_API_TOKEN", "")
    if len(token) < 32:
        raise ValueError("Set LUMENTRAIL_API_TOKEN to a random value of at least 32 characters")
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("LUMENTRAIL_BEHIND_TLS_PROXY") != "1":
        raise ValueError("Non-local binding requires a TLS reverse proxy and LUMENTRAIL_BEHIND_TLS_PROXY=1")
    embedder = make_embedder(embedding)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"):
                self.send_error(401)
                return
            parsed = urlsplit(self.path)
            if parsed.path != "/search":
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            question = query.get("question", [""])[0]
            if len(question) > 500:
                self.send_error(400, "Question too long")
                return
            try:
                with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
                    connection.row_factory = sqlite3.Row
                    hits = search(connection, question, embedder, limit=3)
                body = json.dumps({"hits": hits, "note": "Evidence only. Not medical advice."}).encode()
            except (ValueError, sqlite3.Error):
                self.send_error(400, "Invalid search request or index")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            # Health-related questions can contain sensitive information.
            pass

    ThreadingHTTPServer((host, port), Handler).serve_forever()

