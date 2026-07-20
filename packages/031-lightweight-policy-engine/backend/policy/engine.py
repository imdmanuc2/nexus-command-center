from __future__ import annotations
from backend.policy.models import PolicyDecision

READ_ONLY = {
    "host.identity", "host.disk-usage", "host.memory", "service.status",
    "service.journal", "bitcoin.rpc.test", "miningcore.pool.readiness",
}
CONFIRMATION_REQUIRED = {
    "service.restart", "service.stop", "host.shutdown", "asset.delete",
}
DENIED = {"shell.execute", "command.execute", "host.arbitrary-command"}

def classify_operation(operation: str) -> str:
    operation = operation.strip().lower()
    if operation in READ_ONLY or operation.endswith((".status", ".readiness", ".diagnostics", ".test")):
        return "read"
    if operation in CONFIRMATION_REQUIRED or operation.endswith((".restart", ".stop", ".shutdown", ".delete")):
        return "destructive"
    if operation.startswith("playbook:"):
        return "playbook"
    return "configuration"

def evaluate_operation(operation: str, *, confirmed: bool = False) -> PolicyDecision:
    operation = str(operation or "").strip()
    if not operation:
        return PolicyDecision("deny", "v1-invalid-operation", operation, "Operation is required.")
    lowered = operation.lower()
    if lowered in DENIED or any(token in lowered for token in ("shell", "arbitrary-command")):
        return PolicyDecision("deny", "v1-deny-arbitrary-command", operation, "Arbitrary command execution is not allowed.")
    classification = classify_operation(operation)
    if classification == "destructive" and not confirmed:
        return PolicyDecision("confirmation_required", "v1-confirm-destructive", operation, "This operation changes service or host state and requires explicit confirmation.", True)
    return PolicyDecision("allow", f"v1-allow-{classification}", operation, "Operation is allowed by the Version 1 policy baseline.")
