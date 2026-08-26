#!/usr/bin/env python3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path as FilePath
from uuid import UUID
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
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
from backend.modules import platform_deployments
from backend.modules import blockchain_management
from backend.modules import platform_operational_state
from backend.modules import platform_operational_profile
from backend.modules import platform_cmdb_lifecycle
from backend.modules import platform_dependencies
from backend.modules import platform_intelligence
from backend.modules import platform_services
from backend.modules import platform_service_operations
from backend.modules import platform_service_membership
from backend.modules import platform_service_impact
from backend.modules import platform_service_maintenance
from backend.modules import platform_change_management
from backend.modules import platform_change_execution
from backend.modules import platform_nodes
from backend.modules import platform_nexus_instances
from backend.modules import metrics
from backend.core.assets import update_asset
from backend.modules import platform_change_rollback
from backend.modules import platform_evidence
from backend.modules import platform_verifications
from backend.core.nexus_identity import runtime_identity
from backend.services.nexus_instance_service import register_local_instance

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


from backend.api import seymour_registration_routes
from backend.api import seymour_telemetry_routes

class NexusHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self):
        length_header = self.headers.get("Content-Length", "0")
        try:
            content_length = int(length_header)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Content-Length header") from exc

        if content_length <= 0:
            return {}

        raw = self.rfile.read(content_length)
        if not raw:
            return {}

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON body") from exc

        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")

        return payload

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
        if seymour_registration_routes.handle_get(self):
            return

        if seymour_telemetry_routes.handle_get(self):
            return

        # Package 049: Operations Evidence & Timeline Integration
        _evidence_url = urlparse(self.path)
        _evidence_path = _evidence_url.path
        _evidence_query = parse_qs(_evidence_url.query)

        if _evidence_path == "/api/evidence":
            status, payload = json_response(platform_evidence.evidence(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/evidence/status":
            status, payload = json_response(platform_evidence.status(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/timeline/operations":
            status, payload = json_response(platform_evidence.timeline(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/recommendations/context":
            status, payload = json_response(platform_evidence.recommendation_context(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path.startswith("/api/evidence/"):
            _evidence_id = _evidence_path.removeprefix("/api/evidence/").strip("/")
            if _evidence_id:
                result = platform_evidence.evidence_detail(_evidence_id)
                response_status = 404 if result.get("status") == "not-found" else 200
                status, payload = json_response(result, response_status)
                return self._send_json(payload, status)

        if _evidence_path.startswith("/api/assets/") and _evidence_path.endswith("/operations"):
            _asset_id = _evidence_path.removeprefix("/api/assets/").removesuffix("/operations").strip("/")
            if _asset_id:
                status, payload = json_response(platform_evidence.asset_operations(_asset_id, _evidence_query))
                return self._send_json(payload, status)

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
        if self.path == "/blockchain.html":
            return self._send_file(
                "frontend/blockchain.html",
                "text/html",
            )
        if self.path == "/cmdb-object.html" or self.path.startswith("/cmdb-object.html?"):
            return self._send_file("frontend/cmdb-object.html", "text/html")
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
        if self.path == "/deployments.html":
            return self._send_file("frontend/deployments.html", "text/html")
        if self.path == "/operational-state.html":
            return self._send_file("frontend/operational-state.html", "text/html")
        if self.path in {"/operations-center", "/operations-center.html"}:
            return self._send_file(
                "frontend/operations-center.html",
                "text/html",
            )
        if self.path == "/inventory.html":
            return self._send_file("frontend/assets.html", "text/html")
        # Static assets may use cache-busting query parameters.
        # Resolve only the URL path when mapping requests to files.
        static_path = urlparse(self.path).path

        if static_path.startswith("/css/"):
            return self._send_file(
                "frontend" + static_path,
                "text/css",
            )

        if static_path.startswith("/js/"):
            return self._send_file(
                "frontend" + static_path,
                "application/javascript",
            )

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
            "/api/platform/objects": platform.object_list,
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
            "/api/platform/nexus-instances": platform_nexus_instances.instance_list,
            "/api/platform/pools": platform.pool_list,
            "/api/platform/workers": platform.worker_list,
            "/api/platform/fleet": platform.fleet_summary,
            "/api/platform/topology": platform.topology_graph,
            "/api/graph": graph.graph,
            "/api/blockchain/nodes": blockchain.nodes,
            "/api/blockchain/catalog": blockchain_management.catalog,
            "/api/blockchain/operations": blockchain_management.operations,
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
            "/api/platform/dashboard-summary": platform.dashboard_summary,
            "/api/platform/home": platform.home,
    "/api/change-rollbacks/status": platform_change_rollback.status,
    "/api/change-rollbacks/history": platform_change_rollback.history,
        }

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # PACKAGE-048-VERIFICATION-GET-BEGIN
        if parsed.path == "/api/verifications/profiles":
            try:
                result = platform_verifications.profiles(query)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/verifications/runs":
            try:
                result = platform_verifications.runs(query)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path.startswith("/api/verifications/runs/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            try:
                result = platform_verifications.run_detail(run_id)
                status, payload = json_response(result)
            except LookupError as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        # PACKAGE-048-VERIFICATION-GET-END

        if parsed.path.startswith("/api/platform/objects/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 5:
                object_type = parts[3]
                object_id = "/".join(parts[4:])
                try:
                    result = platform.object_detail(object_type, object_id)
                    response_status = 404 if result.get("status") == "not-found" else 200
                    status, payload = json_response(result, response_status)
                except Exception as exc:
                    status, payload = json_response({"status": "error", "error": str(exc)}, 400)
                return self._send_json(payload, status)

        if parsed.path == "/api/health":
            try: status, payload = json_response(platform_service_operations.health())
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},503)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/membership/rules":
            try: status, payload = json_response(platform_service_membership.rules(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/membership/runs":
            try: status, payload = json_response(platform_service_membership.runs(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/dependencies":
            try: status, payload = json_response(platform_service_impact.dependencies(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/services/impact":
            try: status, payload = json_response(platform_service_impact.impact(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/services/root-cause":
            try: status, payload = json_response(platform_service_impact.root_cause(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/change-execution/status":
            try: status, payload = json_response(platform_change_execution.status(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/change-execution/history":
            try: status, payload = json_response(platform_change_execution.history(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/changes":
            try: status, payload = json_response(platform_change_management.list_changes(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/changes/history":
            try: status, payload = json_response(platform_change_management.history(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/changes/templates":
            try: status, payload = json_response(platform_change_management.templates(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/changes/impact-preview":
            try: status, payload = json_response(platform_change_management.impact_preview(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path.startswith("/api/changes/"):
            change_id = parsed.path.rsplit("/", 1)[-1]
            try: status, payload = json_response(platform_change_management.get_change(change_id))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},404)
            return self._send_json(payload, status)
        if parsed.path == "/api/maintenance":
            try: status, payload = json_response(platform_service_maintenance.windows(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/maintenance/active":
            try: status, payload = json_response(platform_service_maintenance.active(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/maintenance/upcoming":
            try: status, payload = json_response(platform_service_maintenance.upcoming(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/maintenance/history":
            try: status, payload = json_response(platform_service_maintenance.history(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/maintenance/impact-preview":
            try: status, payload = json_response(platform_service_maintenance.impact_preview(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)
        if parsed.path == "/api/services/dashboard":
            try: status, payload = json_response(platform_service_operations.dashboard(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/health":
            try: status, payload = json_response(platform_service_operations.service_health(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/incidents":
            try: status, payload = json_response(platform_service_operations.incidents(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/capacity":
            try: status, payload = json_response(platform_service_operations.capacity(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/topology":
            try: status, payload = json_response(platform_services.topology(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/services/detail":
            try: status, payload = json_response(platform_services.detail(query))
            except KeyError as exc: status, payload = json_response({"status":"error","error":f"Service not found: {exc}"},404)
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/intelligence/analyze":
            try: status, payload = json_response(platform_intelligence.analyze(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/intelligence/knowledge":
            try: status, payload = json_response(platform_intelligence.knowledge(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/relationships/catalog":
            try: status, payload = json_response(platform_dependencies.catalog(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/relationships/asset":
            try: status, payload = json_response(platform_dependencies.asset(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/dependency-map":
            try: status, payload = json_response(platform_dependencies.dependency_map(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/lifecycle/asset":
            try: status, payload = json_response(platform_cmdb_lifecycle.asset(query))
            except KeyError as exc: status, payload = json_response({"status":"error","error":str(exc)},404)
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/lifecycle/history":
            try: status, payload = json_response(platform_cmdb_lifecycle.history(query))
            except Exception as exc: status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)
        if parsed.path == "/api/cmdb/operational-profile":
            try:
                status, payload = json_response(platform_operational_profile.asset(query))
            except KeyError as exc:
                status, payload = json_response({"status":"error","error":str(exc)},404)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)

        if parsed.path == "/api/platform/nexus-instance":
            try:
                instance_id = str(
                    query.get("instanceId", [""])[0] or ""
                ).strip()

                if not instance_id:
                    status, payload = json_response(
                        {"error": "Missing instanceId"},
                        400,
                    )
                    return self._send_json(payload, status)

                result = platform_nexus_instances.instance_detail(
                    instance_id
                )

                if result is None:
                    status, payload = json_response(
                        {"error": "Nexus instance not found"},
                        404,
                    )
                    return self._send_json(payload, status)

                status, payload = json_response(result)
                return self._send_json(payload, status)

            except Exception as e:
                status, payload = json_response(
                    {"error": str(e)},
                    500,
                )
                return self._send_json(payload, status)

        if parsed.path == "/api/platform/operational-state/assets":
            try:
                status, payload = json_response(platform_operational_state.assets(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/operational-state/asset":
            try:
                status, payload = json_response(platform_operational_state.asset(query))
            except KeyError as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/operational-state/summary":
            try:
                status, payload = json_response(platform_operational_state.summary())
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/operational-state/history":
            try:
                status, payload = json_response(platform_operational_state.history(query))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/deployments/packages":
            try:
                status, payload = json_response(platform_deployments.packages(query))
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/deployments/jobs":
            try:
                status, payload = json_response(platform_deployments.jobs(query))
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        if parsed.path == "/api/platform/deployments/job":
            try:
                status, payload = json_response(platform_deployments.job(query))
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
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
        if seymour_registration_routes.handle_post(self):
            return

        if seymour_telemetry_routes.handle_post(self):
            return

        # PACKAGE-048-VERIFICATION-POST-BEGIN
        verification_path = urlparse(self.path).path

        if verification_path == "/api/verifications/profiles":
            try:
                result = platform_verifications.create_profile(self._read_json_body())
                status, payload = json_response(result, 201)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if verification_path == "/api/verifications/run":
            try:
                result = platform_verifications.queue(self._read_json_body())
                status, payload = json_response(result, 202)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if verification_path.startswith("/api/verifications/runs/") and verification_path.endswith("/retry"):
            run_id = verification_path.removeprefix("/api/verifications/runs/").removesuffix("/retry").strip("/")
            try:
                result = platform_verifications.retry(run_id)
                status, payload = json_response(result, 202)
            except LookupError as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        # PACKAGE-048-VERIFICATION-POST-END

        parsed = urlparse(self.path)

        # BEGIN PACKAGE 047 CHANGE ROLLBACK POST ROUTES
        if parsed.path == "/api/change-rollbacks":
            try:
                result = platform_change_rollback.create(self._read_json_body())
                status, payload = json_response(result, 201)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/approve":
            try:
                result = platform_change_rollback.approve(self._read_json_body())
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/queue":
            try:
                result = platform_change_rollback.queue(self._read_json_body())
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)
        # END PACKAGE 047 CHANGE ROLLBACK POST ROUTES


        if parsed.path == "/api/changes":
            try:
                data = self._read_json_body()
                status, payload = json_response(platform_change_management.create(data))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)

        if parsed.path.startswith("/api/changes/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "changes":
                change_id, action = parts[2], parts[3]
                try:
                    data = self._read_json_body()
                    if action == "approve":
                        result = platform_change_management.approve(change_id, data)
                    elif action == "execute":
                        result = platform_change_management.execute(change_id, data)
                    elif action == "rollback":
                        result = platform_change_management.rollback(change_id, data)
                    elif action == "cancel":
                        result = platform_change_management.cancel(change_id, data)
                    elif action == "complete":
                        result = platform_change_management.complete(change_id, data)
                    elif action == "fail":
                        result = platform_change_management.fail(change_id, data)
                    else:
                        raise ValueError("Unsupported change action")
                    status, payload = json_response(result)
                except Exception as exc:
                    status, payload = json_response({"status":"error","error":str(exc)},400)
                return self._send_json(payload, status)

        if parsed.path in {
            "/api/maintenance",
            "/api/maintenance/start",
            "/api/maintenance/complete",
            "/api/maintenance/cancel",
        }:
            try:
                data = self._read_json_body()
                if parsed.path == "/api/maintenance":
                    result = platform_service_maintenance.create(data)
                elif parsed.path.endswith("/start"):
                    result = platform_service_maintenance.start(data)
                elif parsed.path.endswith("/complete"):
                    result = platform_service_maintenance.complete(data)
                else:
                    result = platform_service_maintenance.cancel(data)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)

        if parsed.path == "/api/services/membership/reconcile":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length) or b"{}")
                status, payload = json_response(platform_service_membership.reconcile(data))
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)

        if self.path == "/api/cmdb/relationships/upsert":
            try:
                length=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(length) or b"{}")
                status,payload=json_response(platform_dependencies.upsert(data))
            except Exception as exc: status,payload=json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)

        if self.path == "/api/cmdb/lifecycle/update":
            try:
                length=int(self.headers.get("Content-Length","0")); data=json.loads(self.rfile.read(length) or b"{}")
                status,payload=json_response(platform_cmdb_lifecycle.update(data))
            except KeyError as exc: status,payload=json_response({"status":"error","error":str(exc)},404)
            except Exception as exc: status,payload=json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload,status)

        if self.path == "/api/cmdb/operational-profile/update":
            try:
                status, payload = json_response(platform_operational_profile.update(self._read_json_body()))
            except KeyError as exc:
                status, payload = json_response({"status":"error","error":str(exc)},404)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)},400)
            return self._send_json(payload, status)

        if self.path in {"/api/platform/operational-state/set", "/api/platform/operational-state/bulk-set"}:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length) or b"{}")
                result = (platform_operational_state.set_state(data)
                          if self.path.endswith("/set") else platform_operational_state.bulk_set_state(data))
                status, payload = json_response(result)
            except KeyError as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status":"error","error":str(exc)}, 400)
            return self._send_json(payload, status)

        if self.path == "/api/blockchain/deployment-plan":
            try:
                data = self._read_json_body()
                result = blockchain_management.deployment_plan(data)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)},
                    400,
                )
            return self._send_json(payload, status)

        if self.path in {"/api/platform/deployments/register-package", "/api/platform/deployments/create", "/api/platform/deployments/transition"}:
            try:
                data = self._read_json_body()
                if self.path.endswith("register-package"):
                    result = platform_deployments.register(data)
                elif self.path.endswith("/create"):
                    result = platform_deployments.create(data)
                else:
                    result = platform_deployments.transition(data)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
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


def _register_runtime_instance():
    identity = runtime_identity()

    organization_id = str(
        identity.get("organizationId") or ""
    ).strip()
    site_id = str(
        identity.get("siteId") or ""
    ).strip()

    if not organization_id or not site_id:
        print(
            "Nexus runtime identity is unscoped; "
            "automatic instance registration skipped."
        )
        return None

    result = register_local_instance(identity)

    instance = result.get("instance") or {}

    print(
        "Nexus runtime instance registered: "
        f"{instance.get('instance_id', identity.get('instanceId', ''))}"
    )

    return result


def main():
    host = os.getenv("NEXUS_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("NEXUS_HTTP_PORT", "8080"))

    _register_runtime_instance()

    print(f"{APP_NAME} API running on http://{host}:{port}")
    server = ThreadingHTTPServer(
        (host, port),
        NexusHandler,
    )
    server.daemon_threads = True
    server.serve_forever()




if __name__ == "__main__":
    main()
