from __future__ import annotations
import json
from urllib.parse import urlparse
from backend.services import seymour_registration_service

POST_PATH="/api/integrations/seymour/registration"
STATUS_PATH="/api/integrations/seymour/registration/status"


def handle_get(handler) -> bool:
    if urlparse(handler.path).path != STATUS_PATH: return False
    handler._send_json(seymour_registration_service.status())
    return True


def handle_post(handler) -> bool:
    if urlparse(handler.path).path != POST_PATH: return False
    try:
        length=int(handler.headers.get("Content-Length","0"))
        raw=handler.rfile.read(length)
        payload=json.loads(raw.decode("utf-8")) if raw else {}
    except Exception as exc:
        handler._send_json({"status":"error","error":f"Invalid JSON body: {exc}"},400)
        return True
    status,result=seymour_registration_service.receive(
        payload,
        handler.headers.get("Authorization",""),
        handler.headers.get("Idempotency-Key",""),
    )
    handler._send_json(result,status)
    return True
