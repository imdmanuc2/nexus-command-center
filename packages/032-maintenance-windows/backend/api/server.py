#!/usr/bin/env python3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path as FilePath
from uuid import UUID
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from backend.modules import system
from backend.modules import blockchain
from backend.modules import mining_readiness
from backend.modules import connectors
from backend.modules import discovery
from backend.core import discovery as discovery_core
from backend.modules import dashboard
from backend.modules import mining
from backend.modules import fleet
from backend.modules import smc_health
from backend.modules import operations_events
from backend.modules import operations
from backend.modules import assets
from backend.modules import graph
from backend.modules import graph_engine
from backend.modules import graph_diff
from backend.modules import timeline
from backend.modules import relationships
from backend.modules import snapshots
from backend.modules import event_engine
from backend.modules import mission
from backend.modules import scan_registry
from backend.modules import cmdb
from backend.modules import platform_inventory
from backend.modules import platform
from backend.modules import platform_miningcore
from backend.modules import platform_events
from backend.modules import platform_alerts
from backend.modules import platform_context
from backend.modules import platform_recommendations
from backend.modules import platform_automation
from backend.modules import platform_timeline
from backend.modules import platform_operations_center
from backend.modules import platform_operation_sessions
from backend.modules import platform_playbooks
from backend.modules import platform_policies
from backend.modules import platform_maintenance
from backend.modules import platform_nodes
from backend.modules import metrics
from backend.core.assets import update_asset

APP_NAME = "Nexus Command Center"



def _json_default(value):
    """Serialize PostgreSQL and common Python values safely."""

    if isinstance(value, Decimal):
        # PostgreSQL NUMERIC values are commonly returned as Decimal.
        # Preserve whole values as integers and fractional values as floats.
        if value == value.to_integral_value():
            return int(value)

        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, FilePath):
        return str(value)

    if isinstance(value, set):
        return sorted(value, key=str)

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    raise TypeError(
        f"Object of type {value.__class__.__name__} "
        "is not JSON serializable"
    )


def json_response(payload, status=200):
    return status, json.dumps(
        payload,
        indent=2,
        default=_json_default,
    ).encode("utf-8")


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
        if self.path == "/home-v2.html":
            return self._send_file("frontend/home-v2.html", "text/html")
        if self.path == "/map.html":
            return self._send_file("frontend/map.html", "text/html")
        if self.path == "/timeline.html":
            return self._send_file("frontend/timeline.html", "text/html")
        if self.path == "/alerts.html":
            return self._send_file("frontend/alerts.html", "text/html")
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
        if self.path == "/playbooks.html":
            return self._send_file("frontend/playbooks.html", "text/html")
        if self.path == "/policies.html":
            return self._send_file("frontend/policies.html", "text/html")
        if self.path == "/maintenance.html":
            return self._send_file("frontend/maintenance.html", "text/html")
        if self.path == "/operations-center.html":
            return self._send_file(
                "frontend/operations-center.html",
                "text/html",
            )
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
            "/api/fleet/home": fleet.home,
            "/api/smc/health": smc_health.health,
            "/api/mining/summary": mining.summary,
            "/api/mining/workers": mining.workers,
            "/api/mining/pools": mining.pools,
            "/api/mining/coins": mining.coins,
            "/api/assets/relationships": assets.relationships,
            "/api/cmdb/assets": cmdb.assets,
            "/api/cmdb/summary": cmdb.summary,
            "/api/platform/inventory": platform_inventory.summary,
            "/api/platform/relationships": platform.relationship_list,
            "/api/platform/workloads": platform.workload_list,
            "/api/platform/metrics/rollups": metrics.metric_rollups,
            "/api/platform/metrics/history": metrics.metric_history,
            "/api/platform/metrics/current": metrics.current_metrics,
            "/api/platform/metrics": metrics.metrics_summary,
            "/api/platform/miningcore": platform_miningcore.instance_list,
            "/api/platform/events/summary": platform_events.summary,
            "/api/platform/events/recent": platform_events.recent_events,
            "/api/platform/events": platform_events.events,
            "/api/platform/alerts/summary": platform_alerts.summary,
            "/api/platform/alerts/active": platform_alerts.active_alerts,
            "/api/platform/alerts": platform_alerts.alerts,
            "/api/platform/context/health": platform_context.health,
            "/api/platform/context/infrastructure": platform_context.infrastructure,
            "/api/platform/context/mining": platform_context.mining,
            "/api/platform/context/home": platform_context.home,
            "/api/platform/context": platform_context.overview,
            "/api/platform/recommendations/summary": platform_recommendations.summary,
            "/api/platform/recommendations/high-priority": platform_recommendations.high_priority,
            "/api/platform/recommendations": platform_recommendations.recommendations,
            "/api/platform/automation/summary": platform_automation.summary,
            "/api/platform/automation/audit": platform_automation.audit,
            "/api/platform/automation/runs": platform_automation.runs,
            "/api/platform/automation/actions": platform_automation.actions,
            "/api/platform/timeline/summary": platform_timeline.timeline_summary,
            "/api/platform/timeline/latest": platform_timeline.latest,
            "/api/platform/timeline": platform_timeline.timeline,
            "/api/platform/operations-center/snapshot": platform_operations_center.snapshot,
            "/api/platform/operations-center/queue": platform_operations_center.queue,
            "/api/platform/operations-center/status": platform_operations_center.status,
            "/api/platform/operations-center": platform_operations_center.dashboard,
            "/api/platform/nodes": platform_nodes.node_list,
            "/api/platform/pools": platform.pool_list,
            "/api/platform/workers": platform.worker_list,
            "/api/platform/fleet": platform.fleet_summary,
            "/api/platform/topology": platform.topology_graph,
            "/api/graph": graph.graph,
            "/api/blockchain/nodes": blockchain.nodes,
            "/api/operations/mining-readiness": mining_readiness.pools,
            "/api/graph/live": graph_engine.live,
            "/api/graph/rebuild": graph_engine.rebuild,
            "/api/graph/snapshots": graph_engine.snapshots,
            "/api/graph/statistics": graph_engine.statistics,
            "/api/graph/diff": graph_diff.latest,
            "/api/events/live": event_engine.live,
            "/api/events/operations": operations_events.events,
            "/api/operations": operations.available,
            "/api/mission/status": mission.status,
            "/api/timeline/latest": timeline.latest,
            "/api/platform/home": platform.home,
        }

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/platform/maintenance/windows":
            try:
                status, payload = json_response(platform_maintenance.windows(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/platform/maintenance/window":
            try:
                status, payload = json_response(platform_maintenance.window(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/platform/maintenance/status":
            try:
                status, payload = json_response(platform_maintenance.status(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/policies":
            status, payload = json_response(platform_policies.policies(query))
            return self._send_json(payload, status)
        if parsed.path == "/api/policy-decisions":
            status, payload = json_response(platform_policies.decisions(query))
            return self._send_json(payload, status)

        if parsed.path == "/api/playbooks":
            try:
                status, payload = json_response(platform_playbooks.catalog(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/playbooks/detail":
            try:
                status, payload = json_response(platform_playbooks.detail(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/playbooks/runs":
            try:
                status, payload = json_response(platform_playbooks.runs(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/playbooks/run-detail":
            try:
                status, payload = json_response(platform_playbooks.run_detail(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/platform/operation-sessions":
            try:
                status, payload = json_response(platform_operation_sessions.sessions(query))
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/platform/operation-session":
            try:
                status, payload = json_response(platform_operation_sessions.session(query))
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/cmdb/audit":
            asset_id = query.get("assetId", [None])[0]
            action = query.get("action", [None])[0]
            source = query.get("source", [None])[0]
            correlation_id = query.get(
                "correlationId",
                [None],
            )[0]

            try:
                limit = int(query.get("limit", ["200"])[0])
            except (TypeError, ValueError):
                limit = 200

            status, payload = json_response(
                cmdb.audit_events(
                    asset_id=asset_id,
                    action=action,
                    source=source,
                    correlation_id=correlation_id,
                    limit=limit,
                )
            )
            return self._send_json(payload, status)

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

        if self.path in {"/api/platform/maintenance/create", "/api/platform/maintenance/cancel"}:
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = platform_maintenance.create(data) if self.path.endswith("/create") else platform_maintenance.cancel(data)
                status, payload = json_response(result, 200)
                return self._send_json(payload, status)
            except json.JSONDecodeError:
                status, payload = json_response({"status":"error","error":"Invalid JSON body"}, 400)
                return self._send_json(payload, status)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
                return self._send_json(payload, status)

        if self.path == "/api/policies/evaluate":
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                status, payload = json_response(platform_policies.evaluate(data), 200)
                return self._send_json(payload, status)
            except json.JSONDecodeError:
                return self._send_json({"status":"error","error":"Invalid JSON body"}, 400)
            except Exception as exc:
                return self._send_json({"status":"error","error":str(exc)}, 400)

        if self.path in {"/api/playbooks/run", "/api/playbooks/validate"}:
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = platform_playbooks.run(data) if self.path.endswith("/run") else platform_playbooks.validate(data)
                status, payload = json_response(result, 200)
                return self._send_json(payload, status)
            except json.JSONDecodeError:
                status, payload = json_response({"status":"error","error":"Invalid JSON body"}, 400)
                return self._send_json(payload, status)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
                return self._send_json(payload, status)

        if self.path in {
            "/api/platform/automation/request",
            "/api/platform/automation/approve",
            "/api/platform/automation/reject",
            "/api/platform/automation/cancel",
            "/api/platform/automation/process",
        }:
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body or "{}")
                handlers = {
                    "/api/platform/automation/request": platform_automation.request,
                    "/api/platform/automation/approve": platform_automation.approve,
                    "/api/platform/automation/reject": platform_automation.reject,
                    "/api/platform/automation/cancel": platform_automation.cancel,
                    "/api/platform/automation/process": platform_automation.process,
                }
                result = handlers[self.path](data)
                status, payload = json_response(result, 200)
                return self._send_json(payload, status)
            except (ValueError, TypeError) as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
                return self._send_json(payload, status)
            except json.JSONDecodeError:
                status, payload = json_response({"status": "error", "error": "Invalid JSON body"}, 400)
                return self._send_json(payload, status)

        if self.path == "/api/operations/run":
            try:
                length = int(
                    self.headers.get("Content-Length", 0)
                )
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body or "{}")

                action = str(data.get("action", "")).strip()
                target = data.get("target", {})

                if not action:
                    status, payload = json_response(
                        {"error": "Missing action"},
                        400,
                    )
                    return self._send_json(payload, status)

                if not isinstance(target, dict):
                    status, payload = json_response(
                        {"error": "Target must be an object"},
                        400,
                    )
                    return self._send_json(payload, status)

                result = operations.run(action, target)

                response_status = (
                    404
                    if result.get("status") == "error"
                    and result.get("message", "").startswith(
                        "Unknown operation:"
                    )
                    else 200
                )

                status, payload = json_response(
                    result,
                    response_status,
                )
                return self._send_json(payload, status)

            except json.JSONDecodeError:
                status, payload = json_response(
                    {"error": "Invalid JSON request body"},
                    400,
                )
                return self._send_json(payload, status)

            except Exception as e:
                status, payload = json_response(
                    {"error": str(e)},
                    500,
                )
                return self._send_json(payload, status)

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

        if self.path == "/api/discovery/scan-targets":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)

                targets = data.get("targets", [])
                if isinstance(targets, str):
                    targets = [x.strip() for x in targets.replace("\n", ",").split(",") if x.strip()]

                result = scan_registry.scan_targets(targets)
                status, payload = json_response(result)
                return self._send_json(payload, status)

            except Exception as e:
                status, payload = json_response({"error": str(e)}, 500)
                return self._send_json(payload, status)

        if self.path == "/api/discovery/add-system":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
                asset = scan_registry.add_system(data)
                status, payload = json_response({"status": "ok", "asset": asset})
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
    server = ThreadingHTTPServer(
        (host, port),
        NexusHandler,
    )
    server.daemon_threads = True
    server.serve_forever()




if __name__ == "__main__":
    main()
