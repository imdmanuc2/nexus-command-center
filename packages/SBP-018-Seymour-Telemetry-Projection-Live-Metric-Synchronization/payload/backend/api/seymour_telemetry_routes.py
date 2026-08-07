from __future__ import annotations
import json
from urllib.parse import urlparse
from backend.services import seymour_telemetry_service

STATUS_PATH="/api/integrations/seymour/telemetry/status"
RECONCILE_PATH="/api/integrations/seymour/telemetry/reconcile"

def _json_bytes(payload) -> bytes:
    return json.dumps(payload, default=str).encode("utf-8")

def handle_get(handler) -> bool:
    if urlparse(handler.path).path != STATUS_PATH:
        return False
    handler._send_json(_json_bytes(seymour_telemetry_service.status()))
    return True

def handle_post(handler) -> bool:
    if urlparse(handler.path).path != RECONCILE_PATH:
        return False
    handler._send_json(_json_bytes(seymour_telemetry_service.backfill_latest()))
    return True
