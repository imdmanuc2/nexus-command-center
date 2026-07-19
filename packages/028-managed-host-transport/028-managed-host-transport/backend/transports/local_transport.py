from __future__ import annotations

import subprocess
import time
from typing import Sequence

from backend.transports.models import TransportResult, TransportTarget
from backend.transports.redaction import redact_text


class LocalTransport:
    name = "local"

    def execute(self, *, target: TransportTarget, argv: Sequence[str], timeout_seconds: int, secrets=()) -> TransportResult:
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                list(argv), capture_output=True, text=True, shell=False,
                timeout=timeout_seconds, check=False,
            )
            return TransportResult(
                transport=self.name, target_asset_id=target.asset_id,
                exit_code=completed.returncode,
                stdout=redact_text(completed.stdout, secrets),
                stderr=redact_text(completed.stderr, secrets),
                duration_ms=round((time.perf_counter()-started)*1000),
                host_key_verified=True,
                metadata={"localExecution": True},
            )
        except subprocess.TimeoutExpired as exc:
            return TransportResult(
                transport=self.name, target_asset_id=target.asset_id,
                exit_code=124,
                stdout=redact_text(exc.stdout or "", secrets),
                stderr=redact_text(exc.stderr or "", secrets),
                duration_ms=round((time.perf_counter()-started)*1000),
                timed_out=True, host_key_verified=True,
                metadata={"localExecution": True},
            )
