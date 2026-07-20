from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from backend.playbooks.models import PlaybookDefinition, PlaybookStep


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError(f"{path}: install PyYAML or use JSON-compatible YAML") from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: playbook root must be an object")
    return data


def load_playbook(path: Path) -> PlaybookDefinition:
    data = _load_document(path)
    steps = tuple(PlaybookStep(
        step_id=str(item.get("id") or f"step-{index}"),
        name=str(item.get("name") or item.get("capability") or f"Step {index}"),
        capability=str(item.get("capability") or ""),
        parameters=dict(item.get("parameters") or {}),
        when=item.get("when"),
        continue_on_error=bool(item.get("continueOnError", False)),
    ) for index, item in enumerate(data.get("steps") or [], start=1))
    return PlaybookDefinition(
        playbook_id=str(data.get("id") or ""), name=str(data.get("name") or ""),
        version=str(data.get("version") or "1.0.0"),
        description=str(data.get("description") or ""),
        category=str(data.get("category") or "operations"),
        risk_level=str(data.get("riskLevel") or "low"),
        target_types=tuple(str(v) for v in (data.get("targetTypes") or [])),
        variables=dict(data.get("variables") or {}), steps=steps,
        source_path=str(path),
    )
