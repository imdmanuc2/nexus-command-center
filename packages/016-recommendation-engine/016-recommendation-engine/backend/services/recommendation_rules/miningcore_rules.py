from __future__ import annotations

from backend.services.recommendation_rules.base import (
    RecommendationCandidate,
    RecommendationRule,
)


class MiningCoreOfflineRule(RecommendationRule):
    rule_id = "miningcore-offline"

    def evaluate(self, context):
        recommendations = []

        for instance in context["miningcore"]:
            if instance.get("connected"):
                continue

            instance_id = str(instance.get("instanceId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="miningcore",
                    priority="critical",
                    priority_score=97,
                    confidence=0.99,
                    entity_type="miningcore-instance",
                    entity_id=instance_id,
                    title=f"Restore {instance.get('name') or instance_id}",
                    explanation=(
                        "The MiningCore API is not reachable."
                    ),
                    recommended_action=(
                        "Check the MiningCore service, API port, host network, "
                        "PostgreSQL dependency, and application logs."
                    ),
                    evidence={
                        "endpoint": instance.get("endpoint"),
                        "host": instance.get("host"),
                        "status": instance.get("status"),
                    },
                )
            )

        return recommendations


class MiningCoreConsoleRule(RecommendationRule):
    rule_id = "miningcore-console-offline"

    def evaluate(self, context):
        recommendations = []

        for instance in context["miningcore"]:
            if not instance.get("connected"):
                continue
            if instance.get("consoleOnline"):
                continue
            if not instance.get("consoleUrl"):
                continue

            instance_id = str(instance.get("instanceId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="miningcore",
                    priority="medium",
                    priority_score=55,
                    confidence=0.82,
                    entity_type="miningcore-instance",
                    entity_id=instance_id,
                    title=f"Restore console for {instance.get('name') or instance_id}",
                    explanation=(
                        "The MiningCore API is healthy, but its console is offline."
                    ),
                    recommended_action=(
                        "Restart or inspect the local console service."
                    ),
                    evidence={
                        "consoleUrl": instance.get("consoleUrl"),
                        "apiOnline": instance.get("apiOnline"),
                    },
                )
            )

        return recommendations
