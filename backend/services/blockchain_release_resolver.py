from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

_DEFAULT_RELEASE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "releases"
    / "blockchain"
)


class BlockchainReleaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewedArtifact:
    artifact_id: str
    source: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class BlockchainRelease:
    release_id: str
    runtime_version: str
    source_revision: str
    bootstrap: ReviewedArtifact
    runtime: ReviewedArtifact
    payload_manifest_sha256: str

    def evidence(self) -> dict[str, Any]:
        return {
            "releaseId": self.release_id,
            "runtimeVersion": self.runtime_version,
            "sourceRevision": self.source_revision,
            "bootstrap": {
                "artifactId": self.bootstrap.artifact_id,
                "sha256": self.bootstrap.sha256,
            },
            "runtime": {
                "artifactId": self.runtime.artifact_id,
                "sha256": self.runtime.sha256,
                "payloadManifestSha256": self.payload_manifest_sha256,
            },
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BlockchainReleaseResolver:
    def __init__(self, release_root: Path | None = None) -> None:
        self._root = (
            Path(release_root)
            if release_root is not None
            else _DEFAULT_RELEASE_ROOT
        )

    @staticmethod
    def _required_text(data: dict[str, Any], name: str) -> str:
        value = str(data.get(name) or "").strip()
        if not value:
            raise BlockchainReleaseError(
                f"Release metadata missing {name}"
            )
        return value

    @staticmethod
    def _required_sha(data: dict[str, Any], name: str) -> str:
        value = str(data.get(name) or "").strip().lower()
        if not _SHA256_RE.fullmatch(value):
            raise BlockchainReleaseError(
                f"Release metadata has invalid {name}"
            )
        return value

    @staticmethod
    def _safe_file(value: Any, name: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_FILE_RE.fullmatch(text):
            raise BlockchainReleaseError(
                f"Release metadata has invalid {name}"
            )
        return text

    def _artifact(
        self,
        data: dict[str, Any],
        name: str,
    ) -> ReviewedArtifact:
        artifact_id = self._safe_file(
            data.get("artifactId"),
            f"{name}.artifactId",
        )
        filename = self._safe_file(
            data.get("file"),
            f"{name}.file",
        )
        expected_sha = self._required_sha(
            data,
            "sha256",
        )

        source = self._root / "artifacts" / filename

        if not source.is_file():
            raise BlockchainReleaseError(
                f"Reviewed {name} artifact is missing"
            )

        observed_sha = _sha256(source)
        if observed_sha != expected_sha:
            raise BlockchainReleaseError(
                f"Reviewed {name} artifact SHA-256 mismatch"
            )

        return ReviewedArtifact(
            artifact_id=artifact_id,
            source=source,
            sha256=expected_sha,
        )

    def resolve(self) -> BlockchainRelease:
        manifest = self._root / "current.json"

        if not manifest.is_file():
            raise BlockchainReleaseError(
                "Blockchain release manifest is missing"
            )

        try:
            data = json.loads(
                manifest.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise BlockchainReleaseError(
                "Blockchain release manifest is invalid"
            ) from exc

        if not isinstance(data, dict):
            raise BlockchainReleaseError(
                "Blockchain release manifest must be an object"
            )

        if data.get("schemaVersion") != 1:
            raise BlockchainReleaseError(
                "Unsupported blockchain release schema"
            )

        release_id = self._required_text(
            data,
            "releaseId",
        )
        runtime_version = self._required_text(
            data,
            "runtimeVersion",
        )
        source_revision = self._required_text(
            data,
            "sourceRevision",
        )

        bootstrap_data = data.get("bootstrap")
        runtime_data = data.get("runtime")

        if not isinstance(bootstrap_data, dict):
            raise BlockchainReleaseError(
                "Release metadata missing bootstrap"
            )

        if not isinstance(runtime_data, dict):
            raise BlockchainReleaseError(
                "Release metadata missing runtime"
            )

        bootstrap = self._artifact(
            bootstrap_data,
            "bootstrap",
        )
        runtime = self._artifact(
            runtime_data,
            "runtime",
        )

        payload_manifest_sha256 = self._required_sha(
            runtime_data,
            "payloadManifestSha256",
        )

        return BlockchainRelease(
            release_id=release_id,
            runtime_version=runtime_version,
            source_revision=source_revision,
            bootstrap=bootstrap,
            runtime=runtime,
            payload_manifest_sha256=payload_manifest_sha256,
        )
