from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    policy_id: str
    operation: str
    reason: str
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "policyId": self.policy_id,
            "operation": self.operation,
            "reason": self.reason,
            "requiresConfirmation": self.requires_confirmation,
        }
