from __future__ import annotations

import unittest

from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
    resolve_target_platform_profile,
    supported_target_platforms,
)


class BlockchainTargetPlatformTests(unittest.TestCase):
    def test_only_umbrel_is_currently_supported(self):
        self.assertEqual(
            supported_target_platforms(),
            ("umbrel",),
        )

    def test_resolves_reviewed_umbrel_profile(self):
        profile = resolve_target_platform_profile(
            "umbrel"
        )

        self.assertIs(
            profile,
            UMBREL_TARGET_PROFILE,
        )

    def test_unknown_platform_fails_closed(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported target platform",
        ):
            resolve_target_platform_profile(
                "standalone-linux"
            )

    def test_missing_platform_fails_closed(self):
        with self.assertRaisesRegex(
            ValueError,
            "Target platform is required",
        ):
            resolve_target_platform_profile("")

    def test_umbrel_paths_are_reviewed_constants(self):
        profile = UMBREL_TARGET_PROFILE

        self.assertEqual(
            profile.staging_root,
            "/home/umbrel/.seymour-artifacts",
        )
        self.assertEqual(
            profile.runtime_root,
            "/home/umbrel/umbrel/seymour-runtime",
        )

    def test_profile_contains_no_host_identity(self):
        profile = UMBREL_TARGET_PROFILE

        values = [
            str(
                getattr(profile, field)
            )
            for field in profile.__dataclass_fields__
        ]

        joined = "\n".join(values)

        self.assertNotIn(
            "192.168.",
            joined,
        )
        self.assertNotIn(
            ".154",
            joined,
        )
        self.assertNotIn(
            ".155",
            joined,
        )
        self.assertNotIn(
            ".159",
            joined,
        )

    def test_profile_does_not_expose_credentials(self):
        fields = set(
            UMBREL_TARGET_PROFILE.__dataclass_fields__
        )

        forbidden = {
            "host",
            "username",
            "password",
            "identity_file",
            "known_hosts_file",
            "private_key",
        }

        self.assertTrue(
            forbidden.isdisjoint(fields)
        )


if __name__ == "__main__":
    unittest.main()
