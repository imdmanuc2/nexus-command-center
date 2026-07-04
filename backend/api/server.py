#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from backend.modules import system
from backend.modules import connectors
from backend.modules import discovery

APP_NAME = "Nexus Command Center"


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
        routes = {
            "/api/system/status": system.status,
            "/api/connectors/status": connectors.status,
            "/api/discovery/scan": discovery.scan,
        }

        if self.path == "/api":
            status, payload = json_response({
                "message": "Nexus API online",
                "endpoints": sorted(routes.keys())
            })
            return self._send_json(payload, status)

        handler = routes.get(self.path)

        if handler:
            status, payload = json_response(handler())
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
