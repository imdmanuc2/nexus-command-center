from __future__ import annotations
import hmac, os
from typing import Any
from backend.db.repositories import seymour_registration_repository


def _token() -> str:
    return os.environ.get("NEXUS_SEYMOUR_REGISTRATION_TOKEN","").strip()


def authenticate(header: str) -> bool:
    token=_token()
    if not token or not header.startswith("Bearer "): return False
    supplied=header[7:].strip()
    return hmac.compare_digest(supplied.encode(),token.encode())


def receive(payload: dict[str, Any], authorization: str, idempotency_key: str):
    if not authenticate(authorization):
        return 401,{"status":"error","error":"unauthorized"}
    if not idempotency_key:
        return 400,{"status":"error","error":"Idempotency-Key header is required."}
    try:
        return 200,seymour_registration_repository.ingest(payload,idempotency_key)
    except ValueError as exc:
        return 409,{"status":"error","error":str(exc)}
    except Exception as exc:
        return 500,{"status":"error","error":str(exc)}


def status():
    return {
        "status":"ok",
        "receiver":"seymour-registration",
        "authenticationConfigured":bool(_token()),
        "latestRegistration":seymour_registration_repository.latest(),
    }
