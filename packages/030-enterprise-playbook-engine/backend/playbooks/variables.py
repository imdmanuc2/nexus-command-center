from __future__ import annotations
import re
from typing import Any
_TOKEN = re.compile(r"\$\{([A-Za-z0-9_.-]+)\}")

def resolve_variables(value: Any, values: dict[str, Any]) -> Any:
    if isinstance(value, dict): return {k: resolve_variables(v, values) for k, v in value.items()}
    if isinstance(value, list): return [resolve_variables(v, values) for v in value]
    if not isinstance(value, str): return value
    match = _TOKEN.fullmatch(value)
    if match: return values.get(match.group(1), value)
    return _TOKEN.sub(lambda m: str(values.get(m.group(1), m.group(0))), value)

def build_variables(definitions: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for name, definition in definitions.items():
        default = definition.get("default") if isinstance(definition, dict) else definition
        result[name] = supplied.get(name, default)
        required = isinstance(definition, dict) and bool(definition.get("required"))
        if required and result[name] in (None, ""): raise ValueError(f"Missing required variable: {name}")
    unknown = set(supplied) - set(definitions)
    if unknown: raise ValueError(f"Unknown variables: {sorted(unknown)}")
    return result
