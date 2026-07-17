"""Nexus CMDB reconciliation engine.

This is the only discovery-facing component that may promote observations
into authoritative CMDB assets.
"""

from __future__ import annotations

from typing import Any

from backend.core.asset_manager import (
    get_assets_list,
    upsert_managed_asset,
)
from backend.core.identity_engine import find_best_match
from backend.core.observation_engine import append_observation


def _asset_payload(
    observation: dict[str, Any],
    *,
    existing_asset: dict[str, Any] | None = None,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    raw = dict(observation.get("raw") or {})
    identity = observation.get("identity") or {}
    classification = (
        observation.get("classification") or {}
    )
    compute = observation.get("compute") or {}

    payload = {
        **(existing_asset or {}),
        **raw,
        "ip": (
            identity.get("ip")
            or raw.get("ip")
            or (existing_asset or {}).get("ip")
        ),
        "macAddress": (
            identity.get("macAddress")
            or raw.get("macAddress")
            or (existing_asset or {}).get(
                "macAddress"
            )
            or ""
        ),
        "serialNumber": (
            identity.get("serialNumber")
            or raw.get("serialNumber")
            or (existing_asset or {}).get(
                "serialNumber"
            )
            or ""
        ),
        "hostname": (
            identity.get("hostname")
            or raw.get("hostname")
            or (existing_asset or {}).get(
                "hostname"
            )
            or ""
        ),
        "machineUuid": (
            identity.get("machineUuid")
            or raw.get("machineUuid")
            or (existing_asset or {}).get(
                "machineUuid"
            )
            or ""
        ),
        "sshHostKey": (
            identity.get("sshHostKey")
            or raw.get("sshHostKey")
            or (existing_asset or {}).get(
                "sshHostKey"
            )
            or ""
        ),
        "workerId": (
            identity.get("workerId")
            or raw.get("workerId")
            or (existing_asset or {}).get(
                "workerId"
            )
            or ""
        ),
        "poolId": (
            identity.get("poolId")
            or raw.get("poolId")
            or (existing_asset or {}).get(
                "poolId"
            )
            or ""
        ),
        "assetType": (
            classification.get("assetType")
            or raw.get("assetType")
            or raw.get("type")
            or (existing_asset or {}).get(
                "assetType"
            )
            or "unknown"
        ),
        "primaryRole": (
            classification.get("primaryRole")
            or raw.get("primaryRole")
            or (existing_asset or {}).get(
                "primaryRole"
            )
            or ""
        ),
        "purpose": (
            classification.get("purpose")
            or raw.get("purpose")
            or (existing_asset or {}).get(
                "purpose"
            )
            or ""
        ),
        "computeProfile": (
            compute.get("computeProfile")
            or raw.get("computeProfile")
            or (existing_asset or {}).get(
                "computeProfile"
            )
            or {}
        ),
        "components": (
            compute.get("components")
            or raw.get("components")
            or (existing_asset or {}).get(
                "components"
            )
            or []
        ),
        "capabilities": (
            compute.get("capabilities")
            or raw.get("capabilities")
            or (existing_asset or {}).get(
                "capabilities"
            )
            or []
        ),
        "workloads": (
            compute.get("workloads")
            or raw.get("workloads")
            or (existing_asset or {}).get(
                "workloads"
            )
            or []
        ),
        "managed": True,
        "lifecycleStatus": "managed",
        "createdAutomatically": False,

        # Audit context. The CMDB asset manager should strip these
        # before persistence and attach them to the audit event.
        "_actorType": "system",
        "_actorId": actor_id,
        "_source": "reconciliation-engine",
        "_reason": (
            "Promote approved discovery observation "
            "into Nexus CMDB"
        ),
        "_correlationId": observation.get(
            "correlationId"
        ),
        "_confidence": observation.get(
            "confidence"
        ),
    }

    if existing_asset and existing_asset.get("id"):
        payload["id"] = existing_asset["id"]

    return payload


def reconcile_observation(
    payload: dict[str, Any],
    *,
    source: str = "discovery",
    observer_id: str = "nexus",
    approve_new: bool = False,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    observation = append_observation(
        payload,
        source=source,
        observer_id=observer_id,
    )

    assets = get_assets_list()
    identity_result = find_best_match(
        observation,
        assets,
    )

    observation["decision"] = identity_result[
        "decision"
    ]
    observation["confidence"] = identity_result[
        "confidence"
    ]

    match = identity_result.get("match")
    existing_asset = None

    if match:
        existing_asset = next(
            (
                asset
                for asset in assets
                if asset.get("id")
                == match.get("assetId")
            ),
            None,
        )

    if (
        identity_result["decision"] == "match"
        and existing_asset
    ):
        observation["status"] = "reconciled"
        observation["matchedAssetId"] = (
            existing_asset.get("id")
        )

        asset = upsert_managed_asset(
            _asset_payload(
                observation,
                existing_asset=existing_asset,
                actor_id=actor_id,
            )
        )

        return {
            "status": "reconciled",
            "decision": "matched-existing",
            "confidence": identity_result[
                "confidence"
            ],
            "observation": observation,
            "identity": identity_result,
            "asset": asset,
        }

    if identity_result["decision"] == "conflict":
        observation["status"] = "conflict"

        return {
            "status": "review-required",
            "decision": "conflict",
            "confidence": identity_result[
                "confidence"
            ],
            "observation": observation,
            "identity": identity_result,
            "asset": None,
        }

    if (
        identity_result["decision"] == "review"
        and not approve_new
    ):
        observation["status"] = "review"

        return {
            "status": "review-required",
            "decision": "possible-match",
            "confidence": identity_result[
                "confidence"
            ],
            "observation": observation,
            "identity": identity_result,
            "asset": None,
        }

    if not approve_new:
        observation["status"] = "pending"

        return {
            "status": "pending",
            "decision": "new-candidate",
            "confidence": identity_result[
                "confidence"
            ],
            "observation": observation,
            "identity": identity_result,
            "asset": None,
        }

    observation["status"] = "reconciled"
    observation["decision"] = "created-new"

    asset = upsert_managed_asset(
        _asset_payload(
            observation,
            actor_id=actor_id,
        )
    )

    observation["matchedAssetId"] = asset.get("id")

    return {
        "status": "reconciled",
        "decision": "created-new",
        "confidence": identity_result[
            "confidence"
        ],
        "observation": observation,
        "identity": identity_result,
        "asset": asset,
    }
