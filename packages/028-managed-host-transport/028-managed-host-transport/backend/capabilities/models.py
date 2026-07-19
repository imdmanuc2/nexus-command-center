from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability_id: str
    description: str
    risk_level: str
    requires_approval: bool
    timeout_seconds: int
    build_argv: Callable[[dict[str, Any]], list[str]]
    verify_argv: Callable[[dict[str, Any]], list[str]] | None = None
    allowed_parameters: frozenset[str] = field(default_factory=frozenset)
