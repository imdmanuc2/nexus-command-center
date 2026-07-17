from __future__ import annotations

from backend.services.recommendation_rules.base import (
    RecommendationCandidate,
    RecommendationRule,
)


class CriticalAlertRule(RecommendationRule):
    rule_id = "critical-alert-review"

    def evaluate(self, context):
        recommendations = []

        for alert in context["activeAlerts"]:
            if alert.get("severity") != "critical":
                continue

            alert_id = str(alert.get("alertId") or "unknown")
            entity_type = str(alert.get("entityType") or "alert")
            entity_id = str(alert.get("entityId") or alert_id)

            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="operations",
                    priority="critical",
                    priority_score=100,
                    confidence=1.0,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=alert.get("title") or "Review critical alert",
                    explanation=(
                        alert.get("message")
                        or "A critical active alert requires operator attention."
                    ),
                    recommended_action=(
                        alert.get("recommendedAction")
                        or "Investigate and restore the affected resource."
                    ),
                    evidence={
                        "alertId": alert_id,
                        "ruleId": alert.get("ruleId"),
                        "occurrenceCount": alert.get("occurrenceCount"),
                    },
                )
            )

        return recommendations
