from __future__ import annotations

from backend.services.recommendation_rules.base import (
    RecommendationCandidate,
    RecommendationRule,
)


class OfflineWorkerRule(RecommendationRule):
    rule_id = "worker-offline"

    def evaluate(self, context):
        recommendations = []

        for worker in context["workers"]:
            status = str(worker.get("status") or "").lower()
            if status not in {"offline", "down", "stale", "error"}:
                continue

            worker_id = str(worker.get("workerId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="mining",
                    priority="critical",
                    priority_score=95,
                    confidence=0.98,
                    entity_type="worker",
                    entity_id=worker_id,
                    title=f"Restore worker {worker_id}",
                    explanation=(
                        "The persisted worker state is offline or stale."
                    ),
                    recommended_action=(
                        "Check power, Ethernet connectivity, miner status, "
                        "and its configured pool endpoint."
                    ),
                    evidence={
                        "status": status,
                        "assetId": worker.get("assetId"),
                        "poolInstanceId": worker.get("poolInstanceId"),
                    },
                )
            )

        return recommendations


class ZeroHashrateWorkerRule(RecommendationRule):
    rule_id = "worker-zero-hashrate"

    def evaluate(self, context):
        recommendations = []

        for worker in context["workers"]:
            status = str(worker.get("status") or "").lower()
            hashrate = float(worker.get("currentHashrate") or 0)

            if status != "online" or hashrate > 0:
                continue

            worker_id = str(worker.get("workerId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="mining",
                    priority="high",
                    priority_score=82,
                    confidence=0.88,
                    entity_type="worker",
                    entity_id=worker_id,
                    title=f"Investigate idle worker {worker_id}",
                    explanation=(
                        "The worker is online but currently reports no hashrate."
                    ),
                    recommended_action=(
                        "Verify the mining process, pool assignment, wallet "
                        "configuration, and stratum connectivity."
                    ),
                    evidence={
                        "status": status,
                        "currentHashrate": hashrate,
                        "poolInstanceId": worker.get("poolInstanceId"),
                    },
                )
            )

        return recommendations
