from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionResult:
    status: str
    executor: str
    action: str
    entity_type: str
    entity_id: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    safe_noop: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "status": payload["status"],
            "executor": payload["executor"],
            "action": payload["action"],
            "entityType": payload["entity_type"],
            "entityId": payload["entity_id"],
            "summary": payload["summary"],
            "details": payload["details"],
            "durationMs": payload["duration_ms"],
            "safeNoop": payload["safe_noop"],
        }
