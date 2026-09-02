"""Canonical externally reachable endpoint for the Nexus peer protocol."""

from __future__ import annotations

import os
from collections.abc import Mapping

from backend.services import nexus_peer_pairing_service


ADVERTISE_URL_ENV = "NEXUS_PEER_ADVERTISE_URL"


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def peer_advertise_url(
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Return the explicitly configured callback URL for this Nexus.

    The peer listener bind address is deliberately not used to infer this
    value. A bind address such as 0.0.0.0 describes where the local process
    listens, not an address another Nexus can necessarily reach.

    Deployments must explicitly configure NEXUS_PEER_ADVERTISE_URL before
    initiating a peer pairing.
    """

    source = os.environ if environ is None else environ

    value = _text(
        source.get(ADVERTISE_URL_ENV)
    )

    if not value:
        raise RuntimeError(
            "NEXUS_PEER_ADVERTISE_URL is not configured"
        )

    try:
        normalized = (
            nexus_peer_pairing_service
            .normalize_peer_base_url(value)
        )
    except ValueError as exc:
        raise RuntimeError(
            "NEXUS_PEER_ADVERTISE_URL is invalid"
        ) from exc

    return normalized
