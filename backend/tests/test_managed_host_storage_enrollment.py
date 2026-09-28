from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.services.managed_host_storage_enrollment_service import (
    build_storage_asset,
    enroll_storage_candidate,
    storage_candidates_from_discovery,
)


HOST_ID = "asset-host-test-001"


def host_with_mounts(mounts):
    return {
        "id": HOST_ID,
        "observedState": {
            "managedHostDiscovery": {
                "storage": {
                    "mounts": mounts,
                }
            }
        },
    }


class ManagedHostStorageEnrollmentTests(unittest.TestCase):

    def test_local_storage_identity_is_deterministic(self):
        host = host_with_mounts([
            {
                "source": "/dev/sdb1",
                "target": "/mnt/blockchain",
                "filesystem": "ext4",
            }
        ])

        first = storage_candidates_from_discovery(host)
        second = storage_candidates_from_discovery(host)

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)

        self.assertEqual(
            first[0]["assetId"],
            second[0]["assetId"],
        )

        self.assertTrue(
            first[0]["assetId"].startswith(
                "asset-storage-"
            )
        )

        self.assertEqual(
            first[0]["hostAssetId"],
            HOST_ID,
        )

        self.assertEqual(
            first[0]["assetType"],
            "storage",
        )

        self.assertFalse(
            first[0]["networkStorage"]
        )

        self.assertFalse(
            first[0]["approved"]
        )

    def test_duplicate_mount_views_collapse_to_one_storage_candidate(self):
        host = host_with_mounts([
            {
                "source": "/dev/sdb1",
                "target": "/mnt/blockchain",
                "filesystem": "ext4",
            },
            {
                "source": "/dev/sdb1",
                "target": "/mnt/root/blockchain",
                "filesystem": "ext4",
            },
        ])

        candidates = storage_candidates_from_discovery(
            host
        )

        self.assertEqual(len(candidates), 1)

        candidate = candidates[0]

        self.assertEqual(
            candidate["mountPath"],
            "/mnt/blockchain",
        )

        self.assertEqual(
            candidate["mountPaths"],
            [
                "/mnt/blockchain",
                "/mnt/root/blockchain",
            ],
        )

    def test_network_storage_identity_is_not_host_specific(self):
        mount = {
            "source": "storage.example:/chains",
            "target": "/mnt/chains",
            "filesystem": "nfs4",
        }

        first = storage_candidates_from_discovery(
            host_with_mounts([mount])
        )[0]

        other_host = {
            "id": "asset-host-test-002",
            "observedState": {
                "managedHostDiscovery": {
                    "storage": {
                        "mounts": [mount],
                    }
                }
            },
        }

        second = storage_candidates_from_discovery(
            other_host
        )[0]

        self.assertEqual(
            first["assetId"],
            second["assetId"],
        )

        self.assertEqual(
            first["assetType"],
            "network-storage",
        )

        self.assertTrue(
            first["networkStorage"]
        )

    def test_unapproved_candidate_fails_closed(self):
        candidate = storage_candidates_from_discovery(
            host_with_mounts([
                {
                    "source": "/dev/sdb1",
                    "target": "/mnt/blockchain",
                    "filesystem": "ext4",
                }
            ])
        )[0]

        with self.assertRaisesRegex(
            ValueError,
            "explicitly approved",
        ):
            build_storage_asset(candidate)

    def test_planned_enrollment_does_not_write(self):
        candidate = storage_candidates_from_discovery(
            host_with_mounts([
                {
                    "source": "/dev/sdb1",
                    "target": "/mnt/blockchain",
                    "filesystem": "ext4",
                }
            ])
        )[0]

        candidate = {
            **candidate,
            "approved": True,
        }

        with (
            patch(
                "backend.services."
                "managed_host_storage_enrollment_service."
                "upsert_managed_asset"
            ) as asset_write,
            patch(
                "backend.services."
                "managed_host_storage_enrollment_service."
                "upsert_relationship"
            ) as relationship_write,
        ):
            result = enroll_storage_candidate(
                candidate,
                execute=False,
            )

        self.assertEqual(
            result["status"],
            "planned",
        )

        self.assertTrue(
            result["executable"]
        )

        self.assertEqual(
            result["asset"]["id"],
            candidate["assetId"],
        )

        self.assertEqual(
            result["relationship"]["sourceId"],
            HOST_ID,
        )

        self.assertEqual(
            result["relationship"]["targetId"],
            candidate["assetId"],
        )

        self.assertEqual(
            result["relationship"]["relationshipType"],
            "mounts",
        )

        asset_write.assert_not_called()
        relationship_write.assert_not_called()

    def test_execute_requires_canonical_host(self):
        candidate = storage_candidates_from_discovery(
            host_with_mounts([
                {
                    "source": "/dev/sdb1",
                    "target": "/mnt/blockchain",
                    "filesystem": "ext4",
                }
            ])
        )[0]

        candidate = {
            **candidate,
            "approved": True,
        }

        with patch(
            "backend.services."
            "managed_host_storage_enrollment_service."
            "get_assets_list",
            return_value=[],
        ):
            with self.assertRaisesRegex(
                ValueError,
                "canonical CMDB host asset",
            ):
                enroll_storage_candidate(
                    candidate,
                    execute=True,
                )

    def test_execute_persists_asset_and_mount_relationship(self):
        candidate = storage_candidates_from_discovery(
            host_with_mounts([
                {
                    "source": "/dev/sdb1",
                    "target": "/mnt/blockchain",
                    "filesystem": "ext4",
                }
            ])
        )[0]

        candidate = {
            **candidate,
            "approved": True,
        }

        persisted_asset = {
            "id": candidate["assetId"],
            "assetType": "storage",
        }

        persisted_relationship = {
            "relationshipType": "mounts",
            "sourceId": HOST_ID,
            "targetId": candidate["assetId"],
        }

        with (
            patch(
                "backend.services."
                "managed_host_storage_enrollment_service."
                "get_assets_list",
                return_value=[{"id": HOST_ID}],
            ),
            patch(
                "backend.services."
                "managed_host_storage_enrollment_service."
                "upsert_managed_asset",
                return_value=persisted_asset,
            ) as asset_write,
            patch(
                "backend.services."
                "managed_host_storage_enrollment_service."
                "upsert_relationship",
                return_value=persisted_relationship,
            ) as relationship_write,
        ):
            result = enroll_storage_candidate(
                candidate,
                execute=True,
            )

        self.assertEqual(
            result["status"],
            "enrolled",
        )

        self.assertEqual(
            result["asset"],
            persisted_asset,
        )

        self.assertEqual(
            result["relationship"],
            persisted_relationship,
        )

        asset_write.assert_called_once()
        relationship_write.assert_called_once()

        relationship = (
            relationship_write.call_args.args[0]
        )

        self.assertEqual(
            relationship["sourceType"],
            "asset",
        )

        self.assertEqual(
            relationship["sourceId"],
            HOST_ID,
        )

        self.assertEqual(
            relationship["relationshipType"],
            "mounts",
        )

        self.assertEqual(
            relationship["targetType"],
            "asset",
        )

        self.assertEqual(
            relationship["targetId"],
            candidate["assetId"],
        )

        self.assertTrue(
            relationship["approved"]
        )



class ManagedHostRugixStorageProjectionRegressionTests(
    unittest.TestCase
):
    def test_local_bind_subpath_views_project_backing_storage(
        self,
    ):
        from backend.services.\
managed_host_storage_enrollment_service import (
            storage_candidates_from_discovery,
        )

        host = {
            "id": "asset-host-umbrel",
            "observedState": {
                "managedHostDiscovery": {
                    "storage": {
                        "mounts": [
                            {
                                "source": "/dev/sda6",
                                "target": (
                                    "/run/rugix/mounts/data"
                                ),
                                "filesystem": "ext4",
                                "networkStorage": False,
                            },
                            {
                                "source": (
                                    "/dev/sda6"
                                    "[/state/default/persist/data]"
                                ),
                                "target": "/data",
                                "filesystem": "ext4",
                                "networkStorage": False,
                            },
                            {
                                "source": (
                                    "/dev/sda6"
                                    "[/state/default/persist/data/"
                                    "umbrel-os/home]"
                                ),
                                "target": "/home",
                                "filesystem": "ext4",
                                "networkStorage": False,
                            },
                            {
                                "source": (
                                    "/dev/sda6"
                                    "[/state/default/persist/data/"
                                    "umbrel-os/var/log]"
                                ),
                                "target": "/var/log",
                                "filesystem": "ext4",
                                "networkStorage": False,
                            },
                        ],
                    },
                },
            },
        }

        candidates = storage_candidates_from_discovery(
            host
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.get("source"),
            "/dev/sda6",
        )
        self.assertEqual(
            candidate.get("filesystem"),
            "ext4",
        )
        self.assertFalse(
            candidate.get("networkStorage")
        )
        self.assertEqual(
            candidate.get("mountPath"),
            "/data",
        )

        mount_paths = candidate.get(
            "mountPaths"
        ) or []

        self.assertIn(
            "/data",
            mount_paths,
        )
        self.assertIn(
            "/home",
            mount_paths,
        )
        self.assertIn(
            "/var/log",
            mount_paths,
        )
        self.assertNotIn(
            "/run/rugix/mounts/data",
            mount_paths,
        )

    def test_excluded_run_only_mounts_do_not_project(
        self,
    ):
        from backend.services.\
managed_host_storage_enrollment_service import (
            storage_candidates_from_discovery,
        )

        host = {
            "id": "asset-host-umbrel",
            "observedState": {
                "managedHostDiscovery": {
                    "storage": {
                        "mounts": [
                            {
                                "source": "/dev/sda1",
                                "target": (
                                    "/run/rugix/mounts/config"
                                ),
                                "filesystem": "vfat",
                                "networkStorage": False,
                            },
                            {
                                "source": "/dev/sda5",
                                "target": (
                                    "/run/rugix/mounts/system"
                                ),
                                "filesystem": "ext4",
                                "networkStorage": False,
                            },
                        ],
                    },
                },
            },
        }

        candidates = storage_candidates_from_discovery(
            host
        )

        self.assertEqual(
            candidates,
            [],
        )

if __name__ == "__main__":
    unittest.main()
