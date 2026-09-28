from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetPlatformProfile:
    platform_id: str
    staging_root: str
    runtime_root: str
    lifecycle_adapter_id: str

    test_path: str
    python3_path: str
    tar_path: str
    sha256sum_path: str
    rm_path: str


UMBREL_TARGET_PROFILE = TargetPlatformProfile(
    platform_id="umbrel",
    staging_root="/home/umbrel/.seymour-artifacts",
    runtime_root="/home/umbrel/umbrel/seymour-runtime",
    lifecycle_adapter_id="umbrel",
    test_path="/usr/bin/test",
    python3_path="/usr/bin/python3",
    tar_path="/usr/bin/tar",
    sha256sum_path="/usr/bin/sha256sum",
    rm_path="/usr/bin/rm",
)


_TARGET_PLATFORM_PROFILES = {
    UMBREL_TARGET_PROFILE.platform_id: UMBREL_TARGET_PROFILE,
}


def resolve_target_platform_profile(
    platform_id: str,
) -> TargetPlatformProfile:
    normalized = str(platform_id or "").strip()

    if not normalized:
        raise ValueError(
            "Target platform is required"
        )

    profile = _TARGET_PLATFORM_PROFILES.get(
        normalized
    )

    if profile is None:
        raise ValueError(
            f"Unsupported target platform: {normalized}"
        )

    return profile


def supported_target_platforms() -> tuple[str, ...]:
    return tuple(
        sorted(_TARGET_PLATFORM_PROFILES)
    )
