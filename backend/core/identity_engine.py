"""Evidence-based identity matching for Nexus CMDB assets."""

from __future__ import annotations

from typing import Any


AUTO_MATCH_THRESHOLD = 90
REVIEW_THRESHOLD = 50


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _identity_value(
    record: dict[str, Any],
    key: str,
) -> str:
    identity = record.get("identity")

    if isinstance(identity, dict):
        value = identity.get(key)

        if value not in (None, ""):
            return _string(value)

    return _string(record.get(key))


def score_asset_match(
    observation: dict[str, Any],
    asset: dict[str, Any],
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    score = 0

    checks = [
        ("machineUuid", 120),
        ("serialNumber", 110),
        ("sshHostKey", 100),
        ("macAddress", 95),
        ("workerId", 45),
        ("hostname", 30),
        ("ip", 25),
    ]

    for field, weight in checks:
        observed = _identity_value(
            observation,
            field,
        )
        existing = _identity_value(
            asset,
            field,
        )

        if not observed or not existing:
            continue

        if observed == existing:
            score += weight
            evidence.append({
                "field": field,
                "value": observed,
                "weight": weight,
            })
        elif field in {
            "machineUuid",
            "serialNumber",
            "sshHostKey",
            "macAddress",
        }:
            conflicts.append({
                "field": field,
                "observed": observed,
                "existing": existing,
            })

    observed_worker = _identity_value(
        observation,
        "workerId",
    )
    existing_worker = _identity_value(
        asset,
        "workerId",
    )

    observed_pool = _identity_value(
        observation,
        "poolId",
    )
    existing_pool = _identity_value(
        asset,
        "poolId",
    )

    if (
        observed_worker
        and existing_worker
        and observed_worker == existing_worker
        and observed_pool
        and existing_pool
        and observed_pool == existing_pool
    ):
        score += 35
        evidence.append({
            "field": "workerId+poolId",
            "value": (
                f"{observed_worker}@{observed_pool}"
            ),
            "weight": 35,
        })

    observed_type = _string(
        observation.get("classification", {}).get(
            "assetType"
        )
        or observation.get("assetType")
    )

    existing_type = _string(
        asset.get("assetType")
        or asset.get("canonicalType")
        or asset.get("type")
    )

    if (
        observed_type
        and existing_type
        and observed_type != "unknown"
        and observed_type == existing_type
    ):
        score += 10
        evidence.append({
            "field": "assetType",
            "value": observed_type,
            "weight": 10,
        })

    # Strong identity contradictions must prevent an automatic merge.
    if conflicts:
        score = min(score, REVIEW_THRESHOLD - 1)

    confidence = min(score, 100)

    return {
        "assetId": asset.get("id"),
        "assetName": (
            asset.get("friendlyName")
            or asset.get("displayName")
            or asset.get("name")
            or asset.get("ip")
        ),
        "score": score,
        "confidence": confidence,
        "evidence": evidence,
        "conflicts": conflicts,
    }


def find_best_match(
    observation: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = [
        score_asset_match(observation, asset)
        for asset in assets
    ]

    candidates.sort(
        key=lambda item: (
            item.get("score", 0),
            len(item.get("evidence", [])),
        ),
        reverse=True,
    )

    best = candidates[0] if candidates else None

    if not best or best.get("score", 0) <= 0:
        return {
            "decision": "new",
            "confidence": 0,
            "match": None,
            "candidates": candidates[:5],
        }

    if best.get("conflicts"):
        decision = "conflict"
    elif best["confidence"] >= AUTO_MATCH_THRESHOLD:
        decision = "match"
    elif best["confidence"] >= REVIEW_THRESHOLD:
        decision = "review"
    else:
        decision = "new"

    return {
        "decision": decision,
        "confidence": best["confidence"],
        "match": best,
        "candidates": candidates[:5],
    }
