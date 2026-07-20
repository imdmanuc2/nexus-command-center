from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class PlaybookStep:
    step_id: str
    name: str
    capability: str
    parameters: dict[str, Any] = field(default_factory=dict)
    when: str | None = None
    continue_on_error: bool = False

@dataclass(frozen=True)
class PlaybookDefinition:
    playbook_id: str
    name: str
    version: str
    description: str
    category: str
    risk_level: str
    target_types: tuple[str, ...]
    variables: dict[str, Any]
    steps: tuple[PlaybookStep, ...]
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "playbookId": self.playbook_id, "name": self.name,
            "version": self.version, "description": self.description,
            "category": self.category, "riskLevel": self.risk_level,
            "targetTypes": list(self.target_types), "variables": self.variables,
            "stepCount": len(self.steps), "sourcePath": self.source_path,
            "steps": [{"stepId": s.step_id, "name": s.name,
                       "capability": s.capability, "parameters": s.parameters,
                       "when": s.when, "continueOnError": s.continue_on_error}
                      for s in self.steps],
        }
