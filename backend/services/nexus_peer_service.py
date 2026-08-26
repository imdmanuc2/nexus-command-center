"""Authenticated Nexus-to-Nexus peer identity protocol."""

from __future__ import annotations

import hmac
import os
from typing import Any

from backend.core.nexus_identity import require_runtime_scope


PROTOCOL_NAME = "seymour-nexus-peer"
PROTOCOL_VERSION = "1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _token() -> str:
    return _text(os.getenv("NEXUS_PEER_TOKEN"))


def authentication_configured() -> bool:
    return bool(_token())


def authenticate(authorization: str) -> bool:
    token = _token()

    if not token:
        return False

    prefix = "Bearer "

    if not authorization.startswith(prefix):
        return False

    supplied = authorization[len(prefix):].strip()

    if not supplied:
        return False

    return hmac.compare_digest(
        supplied.encode("utf-8"),
        token.encode("utf-8"),
    )


def identity_document() -> dict[str, Any]:
    identity = require_runtime_scope()

    return {
        "status": "ok",
        "protocol": {
            "name": PROTOCOL_NAME,
            "version": PROTOCOL_VERSION,
        },
        "instance": {
            "instanceId": identity["instanceId"],
            "organizationId": identity["organizationId"],
            "organizationName": identity["organizationName"],
            "siteId": identity["siteId"],
            "siteName": identity["siteName"],
            "name": identity["instanceName"],
            "hostname": identity["hostname"],
            "identitySource": identity["identitySource"],
        },
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def identity(
    authorization: str,
) -> tuple[int, dict[str, Any]]:
    if not authenticate(authorization):
        return 401, {
            "status": "error",
            "error": "unauthorized",
        }

    try:
        return 200, identity_document()
    except Exception as exc:
        return 500, {
            "status": "error",
            "error": str(exc),
        }


def status() -> dict[str, Any]:
    return {
        "status": "ok",
        "protocol": PROTOCOL_NAME,
        "protocolVersion": PROTOCOL_VERSION,
        "authenticationConfigured": authentication_configured(),
    }
