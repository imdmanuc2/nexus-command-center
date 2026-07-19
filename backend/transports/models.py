from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TransportTarget:
    asset_id: str
    transport: str
    host: str = ""
    port: int = 22
    username: str = ""
    identity_file: str = ""
    known_hosts_file: str = ""


@dataclass(slots=True)
class TransportResult:
    transport: str
    target_asset_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    host_key_verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "targetAssetId": self.target_asset_id,
            "exitCode": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "durationMs": self.duration_ms,
            "timedOut": self.timed_out,
            "hostKeyVerified": self.host_key_verified,
            "metadata": self.metadata,
        }
