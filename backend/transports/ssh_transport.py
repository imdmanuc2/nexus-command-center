from __future__ import annotations

import os
import subprocess
import time
from typing import Sequence

from backend.transports.models import TransportResult, TransportTarget
from backend.transports.redaction import redact_text


class SshTransport:
    name = "ssh"

    def execute(self, *, target: TransportTarget, argv: Sequence[str], timeout_seconds: int, secrets=()) -> TransportResult:
        if not target.host or not target.username:
            raise ValueError("SSH target requires host and username")
        if not target.known_hosts_file:
            raise ValueError("SSH target requires a dedicated known_hosts_file")
        if not os.path.isfile(target.known_hosts_file):
            raise ValueError("SSH known_hosts_file does not exist")
        if target.identity_file and not os.path.isfile(target.identity_file):
            raise ValueError("SSH identity_file does not exist")

        # Callers supply argv chosen by the capability registry, never a shell string.
        remote = " ".join(_quote(arg) for arg in argv)
        command = [
            "ssh", "-T", "-p", str(target.port),
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={target.known_hosts_file}",
            "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no",
            "-o", "LogLevel=ERROR",
            "-o", f"ConnectTimeout={min(timeout_seconds, 15)}",
        ]
        if target.identity_file:
            command.extend(["-i", target.identity_file])
        command.extend([f"{target.username}@{target.host}", "--", remote])

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, shell=False,
                timeout=timeout_seconds, check=False,
            )
            return TransportResult(
                transport=self.name, target_asset_id=target.asset_id,
                exit_code=completed.returncode,
                stdout=redact_text(completed.stdout, secrets),
                stderr=redact_text(completed.stderr, secrets),
                duration_ms=round((time.perf_counter()-started)*1000),
                host_key_verified=True,
                metadata={"host": target.host, "port": target.port},
            )
        except subprocess.TimeoutExpired as exc:
            return TransportResult(
                transport=self.name, target_asset_id=target.asset_id,
                exit_code=124,
                stdout=redact_text(exc.stdout or "", secrets),
                stderr=redact_text(exc.stderr or "", secrets),
                duration_ms=round((time.perf_counter()-started)*1000),
                timed_out=True, host_key_verified=True,
                metadata={"host": target.host, "port": target.port},
            )


def _quote(value: str) -> str:
    # POSIX single-quote encoding. Values still originate only from validated capability parameters.
    return "'" + str(value).replace("'", "'\"'\"'") + "'"
