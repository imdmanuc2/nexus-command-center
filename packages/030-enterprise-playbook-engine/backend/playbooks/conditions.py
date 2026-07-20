from __future__ import annotations

def evaluate_condition(expression: str | None, context: dict) -> bool:
    if not expression: return True
    normalized = expression.strip().lower()
    if normalized in {"always", "true"}: return True
    if normalized in {"never", "false"}: return False
    if normalized == "previous.status == success": return context.get("previous", {}).get("status") == "success"
    if normalized == "previous.status != success": return context.get("previous", {}).get("status") != "success"
    raise ValueError(f"Unsupported condition: {expression}")
