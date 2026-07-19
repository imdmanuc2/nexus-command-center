from __future__ import annotations

import re
from typing import Any

from backend.capabilities.models import CapabilityDefinition

_SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")
_JOURNAL_LINES_RE = re.compile(r"^[1-9][0-9]{0,3}$")


def _none(_: dict[str, Any]) -> list[str]:
    return []


def _service(params: dict[str, Any]) -> str:
    value = str(params.get("service") or "").strip()
    if not _SERVICE_RE.fullmatch(value):
        raise ValueError("Invalid or missing allow-listed service name")
    return value


def _host_identity(_: dict[str, Any]) -> list[str]:
    return ["/usr/bin/uname", "-a"]


def _disk_usage(_: dict[str, Any]) -> list[str]:
    return ["/bin/df", "-P", "-h"]


def _memory(_: dict[str, Any]) -> list[str]:
    return ["/usr/bin/free", "-m"]


def _service_status(params: dict[str, Any]) -> list[str]:
    return ["/usr/bin/systemctl", "show", _service(params),
            "--property=ActiveState,SubState,LoadState,MainPID", "--no-pager"]


def _service_restart(params: dict[str, Any]) -> list[str]:
    return ["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart", _service(params)]


def _journal(params: dict[str, Any]) -> list[str]:
    lines = str(params.get("lines") or "200")
    if not _JOURNAL_LINES_RE.fullmatch(lines) or int(lines) > 2000:
        raise ValueError("lines must be between 1 and 2000")
    return ["/usr/bin/journalctl", "-u", _service(params), "-n", lines, "--no-pager", "-o", "short-iso"]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CapabilityDefinition] = {}
        self._register_defaults()

    def register(self, item: CapabilityDefinition) -> None:
        if item.capability_id in self._items:
            raise ValueError(f"Duplicate capability: {item.capability_id}")
        self._items[item.capability_id] = item

    def resolve(self, capability_id: str) -> CapabilityDefinition:
        item = self._items.get(capability_id)
        if item is None:
            raise ValueError(f"Capability is not allow-listed: {capability_id}")
        return item

    def validate_parameters(self, item: CapabilityDefinition, params: dict[str, Any]) -> None:
        unknown = set(params) - set(item.allowed_parameters)
        if unknown:
            raise ValueError(f"Unsupported parameters for {item.capability_id}: {sorted(unknown)}")
        item.build_argv(params)
        if item.verify_argv:
            item.verify_argv(params)

    def describe(self):
        return [{
            "capabilityId": item.capability_id,
            "description": item.description,
            "riskLevel": item.risk_level,
            "requiresApproval": item.requires_approval,
            "timeoutSeconds": item.timeout_seconds,
            "allowedParameters": sorted(item.allowed_parameters),
            "postActionVerification": item.verify_argv is not None,
        } for item in self._items.values()]

    def _register_defaults(self) -> None:
        self.register(CapabilityDefinition("host.identity", "Read host kernel and identity information.", "low", False, 15, _host_identity))
        self.register(CapabilityDefinition("host.disk-usage", "Read mounted filesystem capacity.", "low", False, 20, _disk_usage))
        self.register(CapabilityDefinition("host.memory", "Read host memory utilization.", "low", False, 15, _memory))
        self.register(CapabilityDefinition("service.status", "Read a systemd service state.", "low", False, 20, _service_status, allowed_parameters=frozenset({"service"})))
        self.register(CapabilityDefinition("service.restart", "Restart an allow-listed systemd service and verify its state.", "high", True, 90, _service_restart, verify_argv=_service_status, allowed_parameters=frozenset({"service"})))
        self.register(CapabilityDefinition("service.journal", "Collect a bounded systemd journal excerpt.", "low", False, 30, _journal, allowed_parameters=frozenset({"service", "lines"})))


_registry = CapabilityRegistry()


def get_capability_registry() -> CapabilityRegistry:
    return _registry
