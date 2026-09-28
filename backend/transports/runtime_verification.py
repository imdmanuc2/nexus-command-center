from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import TransportTarget
from backend.transports.ssh_transport import SshTransport


class RuntimeVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeVerificationRequest:
    runtime_version: str
    source_revision: str
    payload_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class RuntimeVerificationResult:
    runtime_version: str
    source_revision: str
    payload_manifest_sha256: str
    executable_present: bool
    duration_ms: int
    host_key_verified: bool


class SshRuntimeVerificationTransport:
    def __init__(
        self,
        *,
        profile: TargetPlatformProfile = UMBREL_TARGET_PROFILE,
        transport: SshTransport | None = None,
    ) -> None:
        self._profile = profile
        self._transport = transport or SshTransport()

    @staticmethod
    def _required_text(
        value: str,
        name: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not normalized:
            raise ValueError(
                f"{name} is required"
            )

        if "\x00" in normalized or "\n" in normalized or "\r" in normalized:
            raise ValueError(
                f"Invalid {name}"
            )

        return normalized

    @staticmethod
    def _required_sha(
        value: str,
        name: str,
    ) -> str:
        normalized = str(value or "").strip().lower()

        if len(normalized) != 64:
            raise ValueError(
                f"Invalid {name}"
            )

        if any(
            char not in "0123456789abcdef"
            for char in normalized
        ):
            raise ValueError(
                f"Invalid {name}"
            )

        return normalized

    @staticmethod
    def _run_checked(
        transport: Any,
        *,
        target: TransportTarget,
        argv: list[str],
        timeout_seconds: int,
        check_name: str,
    ):
        result = transport.execute(
            target=target,
            argv=argv,
            timeout_seconds=timeout_seconds,
        )

        if not result.host_key_verified:
            raise RuntimeVerificationError(
                f"{check_name}: host key was not verified"
            )

        if result.timed_out:
            raise RuntimeVerificationError(
                f"{check_name}: operation timed out"
            )

        if result.exit_code != 0:
            raise RuntimeVerificationError(
                f"{check_name}: verification failed"
            )

        return result

    def verify(
        self,
        *,
        target: TransportTarget,
        request: RuntimeVerificationRequest,
        timeout_seconds: int = 30,
    ) -> RuntimeVerificationResult:
        if target.transport != "ssh":
            raise RuntimeVerificationError(
                "Runtime verification requires SSH"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Runtime verification timeout must be positive"
            )

        if self._profile.platform_id != "umbrel":
            raise RuntimeVerificationError(
                "Unsupported target platform profile"
            )

        runtime_version = self._required_text(
            request.runtime_version,
            "runtime_version",
        )
        source_revision = self._required_text(
            request.source_revision,
            "source_revision",
        )
        payload_sha = self._required_sha(
            request.payload_manifest_sha256,
            "payload_manifest_sha256",
        )

        runtime_root = self._profile.runtime_root
        executable = (
            runtime_root
            + "/scripts/seymour-blockchain-install"
        )
        evidence_file = (
            runtime_root
            + "/runtime-installation.json"
        )

        started = time.monotonic()

        self._run_checked(
            self._transport,
            target=target,
            argv=[
                self._profile.test_path,
                "-d",
                runtime_root,
            ],
            timeout_seconds=timeout_seconds,
            check_name="runtime-root",
        )

        self._run_checked(
            self._transport,
            target=target,
            argv=[
                self._profile.test_path,
                "-x",
                executable,
            ],
            timeout_seconds=timeout_seconds,
            check_name="runtime-executable",
        )

        evidence_result = self._run_checked(
            self._transport,
            target=target,
            argv=[
                self._profile.python3_path,
                "-c",
                (
                    "import json,sys;"
                    "p=sys.argv[1];"
                    "d=json.load(open(p,encoding='utf-8'));"
                    "print(json.dumps({"
                    "'runtimeVersion':d.get('runtimeVersion'),"
                    "'sourceRevision':d.get('sourceRevision'),"
                    "'payloadManifestSha256':"
                    "d.get('payloadManifestSha256')"
                    "},sort_keys=True,separators=(',',':')))"
                ),
                evidence_file,
            ],
            timeout_seconds=timeout_seconds,
            check_name="runtime-evidence",
        )

        import json

        try:
            evidence = json.loads(
                evidence_result.stdout.strip()
            )
        except Exception as exc:
            raise RuntimeVerificationError(
                "runtime-evidence: invalid JSON"
            ) from exc

        if not isinstance(evidence, dict):
            raise RuntimeVerificationError(
                "runtime-evidence: invalid result"
            )

        if evidence.get("runtimeVersion") != runtime_version:
            raise RuntimeVerificationError(
                "runtime-evidence: runtime version mismatch"
            )

        if evidence.get("sourceRevision") != source_revision:
            raise RuntimeVerificationError(
                "runtime-evidence: source revision mismatch"
            )

        if (
            evidence.get("payloadManifestSha256")
            != payload_sha
        ):
            raise RuntimeVerificationError(
                "runtime-evidence: payload manifest mismatch"
            )

        duration_ms = max(
            0,
            int(
                (time.monotonic() - started)
                * 1000
            ),
        )

        return RuntimeVerificationResult(
            runtime_version=runtime_version,
            source_revision=source_revision,
            payload_manifest_sha256=payload_sha,
            executable_present=True,
            duration_ms=duration_ms,
            host_key_verified=True,
        )
