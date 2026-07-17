from __future__ import annotations

from backend.services.recommendation_rules.base import (
    RecommendationCandidate,
    RecommendationRule,
)


class BlockchainSyncRule(RecommendationRule):
    rule_id = "blockchain-node-not-synced"

    def evaluate(self, context):
        recommendations = []

        for node in context["nodes"]:
            sync_percent = node.get("syncPercent")
            if sync_percent is None:
                continue

            sync_percent = float(sync_percent)
            if sync_percent >= 99.9:
                continue

            node_id = str(node.get("nodeId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="blockchain",
                    priority="high",
                    priority_score=85,
                    confidence=0.96,
                    entity_type="blockchain-node",
                    entity_id=node_id,
                    title=f"Wait for {node.get('name') or node_id} to synchronize",
                    explanation=(
                        f"The blockchain node is only {sync_percent:.3f}% synced."
                    ),
                    recommended_action=(
                        "Do not depend on this node for production mining "
                        "until synchronization reaches 100%."
                    ),
                    evidence={
                        "syncPercent": sync_percent,
                        "blockHeight": node.get("blockHeight"),
                        "headers": node.get("headers"),
                    },
                )
            )

        return recommendations


class BlockchainRpcRule(RecommendationRule):
    rule_id = "blockchain-rpc-offline"

    def evaluate(self, context):
        recommendations = []

        for node in context["nodes"]:
            if node.get("rpcConnected"):
                continue

            node_id = str(node.get("nodeId") or "unknown")
            recommendations.append(
                RecommendationCandidate(
                    rule_id=self.rule_id,
                    category="blockchain",
                    priority="critical",
                    priority_score=98,
                    confidence=0.99,
                    entity_type="blockchain-node",
                    entity_id=node_id,
                    title=f"Restore RPC access to {node.get('name') or node_id}",
                    explanation=(
                        "The node is persisted but RPC connectivity is unavailable."
                    ),
                    recommended_action=(
                        "Check the node service, RPC credentials, rpcbind, "
                        "rpcallowip, firewall rules, and network reachability."
                    ),
                    evidence={
                        "status": node.get("status"),
                        "host": node.get("host"),
                        "rpcPort": node.get("rpcPort"),
                    },
                )
            )

        return recommendations
