from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecommendationCandidate:
    rule_id: str
    category: str
    priority: str
    priority_score: int
    confidence: float
    entity_type: str
    entity_id: str
    title: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any]


class RecommendationRule:
    rule_id = "base"

    def evaluate(
        self,
        context: dict[str, Any],
    ) -> list[RecommendationCandidate]:
        raise NotImplementedError
