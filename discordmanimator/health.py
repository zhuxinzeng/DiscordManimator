"""Lightweight HTTP health endpoint for platform health checks (e.g. Zeabur)."""

from __future__ import annotations

import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"DiscordManimator is running. This is a Discord bot, not a web app.\n"
                b"Use /health for load-balancer probes.\n"
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        logger.debug("health %s - %s", self.address_string(), format % args)


def start_health_server() -> HTTPServer | None:
    """Bind to PORT (default 8080) on 0.0.0.0 for load-balancer health probes."""
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health")
    thread.start()
    logger.info("Health check server listening on 0.0.0.0:%s", port)
    return server
