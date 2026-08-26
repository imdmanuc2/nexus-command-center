"""Dedicated network listener for the Nexus peer protocol.

This listener deliberately exposes only the authenticated Nexus peer
protocol. It does not use NexusHandler and therefore cannot expose the
general Nexus HTTP API.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from backend.services import nexus_peer_service


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8561

IDENTITY_PATH = "/api/nexus/identity"


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _host() -> str:
    return _text(os.getenv("NEXUS_PEER_HTTP_HOST")) or DEFAULT_HOST


def _port() -> int:
    value = _text(os.getenv("NEXUS_PEER_HTTP_PORT"))

    if not value:
        return DEFAULT_PORT

    port = int(value)

    if port < 1 or port > 65535:
        raise ValueError("NEXUS_PEER_HTTP_PORT must be between 1 and 65535")

    return port


class NexusPeerHandler(BaseHTTPRequestHandler):
    server_version = "SeymourNexusPeer/1"

    def _send_json(self, payload, status=200) -> None:
        body = json.dumps(
            payload,
            default=str,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path != IDENTITY_PATH:
            self._send_json(
                {
                    "status": "error",
                    "error": "not_found",
                },
                404,
            )
            return

        status, result = nexus_peer_service.identity(
            self.headers.get("Authorization", "")
        )

        self._send_json(result, status)

    def do_POST(self) -> None:
        self._send_json(
            {
                "status": "error",
                "error": "method_not_allowed",
            },
            405,
        )

    def do_PUT(self) -> None:
        self.do_POST()

    def do_PATCH(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def log_message(self, format, *args) -> None:
        print(
            "Nexus peer transport:",
            format % args,
            flush=True,
        )


def run() -> None:
    host = _host()
    port = _port()

    server = ThreadingHTTPServer(
        (host, port),
        NexusPeerHandler,
    )

    print(
        f"Nexus peer transport running on http://{host}:{port}",
        flush=True,
    )

    server.serve_forever()


if __name__ == "__main__":
    run()
