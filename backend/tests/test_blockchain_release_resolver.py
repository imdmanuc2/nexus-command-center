from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.services.blockchain_release_resolver import (
    BlockchainReleaseError,
    BlockchainReleaseResolver,
)


class BlockchainReleaseResolverTests(unittest.TestCase):
    def make_release(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        artifacts = root / "artifacts"
        artifacts.mkdir()

        bootstrap = artifacts / "bootstrap.tar.gz"
        runtime = artifacts / "runtime.tar.gz"

        bootstrap.write_bytes(b"bootstrap-reviewed")
        runtime.write_bytes(b"runtime-reviewed")

        boot_sha = hashlib.sha256(
            bootstrap.read_bytes()
        ).hexdigest()
        runtime_sha = hashlib.sha256(
            runtime.read_bytes()
        ).hexdigest()

        payload_sha = "c" * 64

        manifest = {
            "schemaVersion": 1,
            "releaseId": "release-test",
            "runtimeVersion": "1.0.0",
            "sourceRevision": "revision-test",
            "bootstrap": {
                "artifactId": "bootstrap.tar.gz",
                "file": "bootstrap.tar.gz",
                "sha256": boot_sha,
                "artifactVersion": "1.0.0",
            },
            "runtime": {
                "artifactId": "runtime.tar.gz",
                "file": "runtime.tar.gz",
                "sha256": runtime_sha,
                "payloadManifestSha256": payload_sha,
            },
        }

        (root / "current.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        return (
            temp,
            root,
            bootstrap,
            runtime,
            boot_sha,
            runtime_sha,
            payload_sha,
        )

    def test_resolves_reviewed_release(self):
        (
            temp,
            root,
            bootstrap,
            runtime,
            boot_sha,
            runtime_sha,
            payload_sha,
        ) = self.make_release()

        self.addCleanup(temp.cleanup)

        release = BlockchainReleaseResolver(root).resolve()

        self.assertEqual(release.release_id, "release-test")
        self.assertEqual(release.runtime_version, "1.0.0")
        self.assertEqual(release.bootstrap.source, bootstrap)
        self.assertEqual(release.runtime.source, runtime)
        self.assertEqual(release.bootstrap.sha256, boot_sha)
        self.assertEqual(release.runtime.sha256, runtime_sha)
        self.assertEqual(
            release.payload_manifest_sha256,
            payload_sha,
        )

    def test_evidence_does_not_expose_local_source_paths(self):
        temp, root, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        release = BlockchainReleaseResolver(root).resolve()
        evidence = release.evidence()
        encoded = json.dumps(evidence)

        self.assertNotIn(str(root), encoded)
        self.assertNotIn("source", evidence["bootstrap"])
        self.assertNotIn("source", evidence["runtime"])
        self.assertEqual(
            evidence["sourceRevision"],
            "revision-test",
        )

    def test_bootstrap_tamper_fails_closed(self):
        temp, root, bootstrap, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        bootstrap.write_bytes(b"tampered")

        with self.assertRaisesRegex(
            BlockchainReleaseError,
            "bootstrap artifact SHA-256 mismatch",
        ):
            BlockchainReleaseResolver(root).resolve()

    def test_runtime_tamper_fails_closed(self):
        (
            temp,
            root,
            _bootstrap,
            runtime,
            *_,
        ) = self.make_release()
        self.addCleanup(temp.cleanup)

        runtime.write_bytes(b"tampered")

        with self.assertRaisesRegex(
            BlockchainReleaseError,
            "runtime artifact SHA-256 mismatch",
        ):
            BlockchainReleaseResolver(root).resolve()

    def test_absolute_artifact_path_is_rejected(self):
        temp, root, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        path = root / "current.json"
        data = json.loads(path.read_text())
        data["runtime"]["file"] = "/tmp/runtime.tar.gz"
        path.write_text(json.dumps(data))

        with self.assertRaises(BlockchainReleaseError):
            BlockchainReleaseResolver(root).resolve()

    def test_parent_traversal_is_rejected(self):
        temp, root, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        path = root / "current.json"
        data = json.loads(path.read_text())
        data["bootstrap"]["file"] = "../bootstrap.tar.gz"
        path.write_text(json.dumps(data))

        with self.assertRaises(BlockchainReleaseError):
            BlockchainReleaseResolver(root).resolve()

    def test_missing_artifact_fails_closed(self):
        temp, root, _bootstrap, runtime, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        runtime.unlink()

        with self.assertRaisesRegex(
            BlockchainReleaseError,
            "runtime artifact is missing",
        ):
            BlockchainReleaseResolver(root).resolve()

    def test_bad_payload_manifest_sha_is_rejected(self):
        temp, root, *_ = self.make_release()
        self.addCleanup(temp.cleanup)

        path = root / "current.json"
        data = json.loads(path.read_text())
        data["runtime"]["payloadManifestSha256"] = "bad"
        path.write_text(json.dumps(data))

        with self.assertRaises(BlockchainReleaseError):
            BlockchainReleaseResolver(root).resolve()


if __name__ == "__main__":
    unittest.main()
