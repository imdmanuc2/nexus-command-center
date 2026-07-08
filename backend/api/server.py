#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from backend.modules import system
from backend.modules import connectors
from backend.modules import discovery
from backend.modules import dashboard
from backend.modules import mining
from backend.modules import assets
from backend.modules import graph
from backend.modules import graph_engine
from backend.modules import graph_diff
from backend.modules import timeline
from backend.modules import relationships
from backend.modules import snapshots
from backend.modules import event_engine
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
        if self.path == "/analytics.html":
            return self._send_file("frontend/analytics.html", "text/html")
        if self.path == "/assets.html":
            return self._send_file("frontend/assets.html", "text/html")
        if self.path == "/pools.html":
            return self._send_file("frontend/pools.html", "text/html")
        if self.path == "/discovery.html":
            return self._send_file("frontend/discovery.html", "text/html")
        if self.path == "/graph.html":
            return self._send_file("frontend/graph.html", "text/html")
        if self.path == "/inventory.html":
            return self._send_file("frontend/assets.html", "text/html")
        if self.path.startswith("/css/"):
            return self._send_file("frontend" + self.path, "text/css")
        if self.path.startswith("/js/"):
            return self._send_file("frontend" + self.path, "application/javascript")

        routes = {
            "/api/system/status": system.status,
            "/api/connectors/status": connectors.status,
            "/api/discovery/scan": discovery.scan,
            "/api/discovery/topology": discovery.topology,
            "/api/dashboard/summary": dashboard.summary,
            "/api/mining/summary": mining.summary,
            "/api/mining/workers": mining.workers,
            "/api/assets/relationships": assets.relationships,
            "/api/graph": graph.graph,
            "/api/graph/live": graph_engine.live,
            "/api/graph/rebuild": graph_engine.rebuild,
            "/api/graph/snapshots": graph_engine.snapshots,
            "/api/graph/statistics": graph_engine.statistics,
            "/api/graph/diff": graph_diff.latest,
            "/api/events/live": event_engine.live,
            "/api/timeline/latest": timeline.latest,
        }

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/snapshots":
            status, payload = json_response(snapshots.list_snapshots())
            return self._send_json(payload, status)

        if parsed.path == "/api/snapshot":
            file_name = query.get("file", [""])[0]
            if not file_name:
                status, payload = json_response({"error": "Missing file"}, 400)
            else:
                status, payload = json_response(snapshots.get_snapshot(file_name))
            return self._send_json(payload, status)

        if parsed.path == "/api/relationships":
            node_id = query.get("nodeId", [""])[0]
            if not node_id:
                status, payload = json_response({"error": "Missing nodeId"}, 400)
            else:
                status, payload = json_response(relationships.summary(node_id))
            return self._send_json(payload, status)

        if parsed.path == "/api/impact":
            node_id = query.get("nodeId", [""])[0]
            if not node_id:
                status, payload = json_response({"error": "Missing nodeId"}, 400)
            else:
                status, payload = json_response(relationships.impact(node_id))
            return self._send_json(payload, status)

        if self.path == "/api/graph/layout":
            layout_path = Path("backend/data/graph/layout.json")
            if not layout_path.exists():
                layout_path.write_text("{}")
            status, payload = json_response(json.loads(layout_path.read_text()))
            return self._send_json(payload, status)

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
        if self.path == "/api/graph/layout/save":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)

                layout_path = Path("backend/data/graph/layout.json")
                layout_path.parent.mkdir(parents=True, exist_ok=True)
                layout_path.write_text(json.dumps(data, indent=2))

                status, payload = json_response({"success": True})
                return self._send_json(payload, status)
            except Exception as e:
                status, payload = json_response({"error": str(e)}, 500)
                return self._send_json(payload, status)

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
