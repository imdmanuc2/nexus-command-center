#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from backend.modules import system
from backend.modules import connectors
from backend.modules import discovery
from backend.modules import dashboard
from backend.core.assets import update_asset

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

    def _send_file(self, file_path, content_type):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            status, payload = json_response({"error": "File not found"}, 404)
            self._send_json(payload, status)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            return self._send_file("frontend/index.html", "text/html")
        if self.path == "/map.html":
            return self._send_file("frontend/map.html", "text/html")
        if self.path.startswith("/css/"):
            return self._send_file("frontend" + self.path, "text/css")
        if self.path.startswith("/js/"):
            return self._send_file("frontend" + self.path, "application/javascript")

        routes = {
            "/api/system/status": system.status,
            "/api/connectors/status": connectors.status,
            "/api/discovery/scan": discovery.scan,
            "/api/dashboard/summary": dashboard.summary,
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

    def do_POST(self):
        if self.path == "/api/assets/update":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)

                ip = data.get("ip")
                updates = data.get("updates", {})

                if not ip:
                    status, payload = json_response({"error": "Missing ip"}, 400)
                    return self._send_json(payload, status)

                asset = update_asset(ip, updates)
                status, payload = json_response({"success": True, "asset": asset})
                return self._send_json(payload, status)

            except Exception as e:
                status, payload = json_response({"error": str(e)}, 500)
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
