#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from datetime import datetime, timezone

from backend.core.connectors import ConnectorManager

APP_NAME = "Nexus Command Center"
VERSION = "0.1.0-alpha"
BIRTH_DATE = "2026-07-04"

connector_manager = ConnectorManager()


def json_response(payload, status=200):
    return status, json.dumps(payload, indent=2).encode("utf-8")


class NexusHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api":
            status, payload = json_response({
                "message": "Nexus API online",
                "endpoints": [
                    "/api/system/status",
                    "/api/connectors/status"
                ]
            })
            return self._send_json(payload, status)

        if self.path == "/api/system/status":
            status, payload = json_response({
                "platform": "Nexus",
                "app": APP_NAME,
                "version": VERSION,
                "birthDate": BIRTH_DATE,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "services": {
                    "commandCenter": "online",
                    "setupWizard": "planned",
                    "connectorManager": "online",
                    "discoveryEngine": "planned",
                    "signals": "planned"
                }
            })
            return self._send_json(payload, status)

        if self.path == "/api/connectors/status":
            status, payload = json_response({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "connectors": connector_manager.status()
            })
            return self._send_json(payload, status)

        status, payload = json_response({"error": "Not found"}, 404)
        return self._send_json(payload, status)


def main():
    host = "0.0.0.0"
    port = 8080
    print(f"{APP_NAME} API running on http://{host}:{port}")
    HTTPServer((host, port), NexusHandler).serve_forever()


if __name__ == "__main__":
    main()
