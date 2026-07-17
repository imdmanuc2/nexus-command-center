from __future__ import annotations

from typing import Any

from backend.db.repositories.alert_repository import list_alerts
from backend.db.repositories.blockchain_repository import (
    list_blockchain_nodes,
)
from backend.db.repositories.miningcore_repository import (
    list_miningcore_instances,
)
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.recommendation_repository import (
    resolve_missing_recommendations,
    update_engine_state,
    upsert_recommendation,
)
from backend.db.repositories.worker_repository import list_active_workers
from backend.services.recommendation_rules.alert_rules import (
    CriticalAlertRule,
)
from backend.services.recommendation_rules.miningcore_rules import (
    MiningCoreConsoleRule,
    MiningCoreOfflineRule,
)
from backend.services.recommendation_rules.node_rules import (
    BlockchainRpcRule,
    BlockchainSyncRule,
)
from backend.services.recommendation_rules.worker_rules import (
    OfflineWorkerRule,
    ZeroHashrateWorkerRule,
)


RULES = [
    CriticalAlertRule(),
    OfflineWorkerRule(),
    ZeroHashrateWorkerRule(),
    BlockchainRpcRule(),
    BlockchainSyncRule(),
    MiningCoreOfflineRule(),
    MiningCoreConsoleRule(),
]


def evaluate_recommendations() -> dict[str, Any]:
    context = {
        "workers": list_active_workers(),
        "pools": list_pools(),
        "nodes": list_blockchain_nodes(),
        "miningcore": list_miningcore_instances(),
        "activeAlerts": [
            alert
            for alert in list_alerts(limit=250)
            if alert.get("status") in {"open", "acknowledged"}
        ],
    }

    opened = 0
    updated = 0
    active_keys: set[tuple[str, str, str]] = set()

    try:
        for rule in RULES:
            for candidate in rule.evaluate(context):
                active_keys.add(
                    (
                        candidate.rule_id,
                        candidate.entity_type,
                        candidate.entity_id,
                    )
                )

                result = upsert_recommendation(
                    rule_id=candidate.rule_id,
                    category=candidate.category,
                    priority=candidate.priority,
                    priority_score=candidate.priority_score,
                    confidence=candidate.confidence,
                    entity_type=candidate.entity_type,
                    entity_id=candidate.entity_id,
                    title=candidate.title,
                    explanation=candidate.explanation,
                    recommended_action=candidate.recommended_action,
                    evidence=candidate.evidence,
                )

                if result == "opened":
                    opened += 1
                else:
                    updated += 1

        resolved = resolve_missing_recommendations(active_keys)

        update_engine_state(
            status="ok",
            evaluated_rules=len(RULES),
            opened=opened,
            updated=updated,
            resolved=resolved,
        )

        return {
            "status": "ok",
            "source": "nexus-platform-recommendation-engine",
            "evaluatedRules": len(RULES),
            "recommendationsOpened": opened,
            "recommendationsUpdated": updated,
            "recommendationsResolved": resolved,
            "activeCandidates": len(active_keys),
        }

    except Exception as exc:
        update_engine_state(
            status="error",
            evaluated_rules=len(RULES),
            opened=opened,
            updated=updated,
            resolved=0,
            error=str(exc),
        )
        raise
