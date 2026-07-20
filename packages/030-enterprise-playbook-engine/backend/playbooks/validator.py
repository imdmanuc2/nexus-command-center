from __future__ import annotations
import re
from backend.capabilities.registry import get_capability_registry
from backend.playbooks.models import PlaybookDefinition

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_FORBIDDEN = {"command", "shell", "bash", "python", "argv", "script"}


def validate_playbook(playbook: PlaybookDefinition) -> list[str]:
    errors: list[str] = []
    if not _ID.fullmatch(playbook.playbook_id): errors.append("Invalid playbook id")
    if not playbook.name: errors.append("Playbook name is required")
    if not playbook.steps: errors.append("At least one step is required")
    seen: set[str] = set()
    registry = get_capability_registry()
    for step in playbook.steps:
        if step.step_id in seen: errors.append(f"Duplicate step id: {step.step_id}")
        seen.add(step.step_id)
        if not step.capability: errors.append(f"{step.step_id}: capability is required"); continue
        if _FORBIDDEN.intersection(step.parameters):
            errors.append(f"{step.step_id}: embedded commands are forbidden")
        try:
            definition = registry.resolve(step.capability)
            # Validate literal parameters now; template values are validated at run time.
            literal = {k: v for k, v in step.parameters.items()
                       if not (isinstance(v, str) and "${" in v)}
            unknown = set(step.parameters) - set(definition.allowed_parameters)
            if unknown: errors.append(f"{step.step_id}: unsupported parameters {sorted(unknown)}")
            if len(literal) == len(step.parameters): registry.validate_parameters(definition, literal)
        except ValueError as exc:
            errors.append(f"{step.step_id}: {exc}")
    return errors
