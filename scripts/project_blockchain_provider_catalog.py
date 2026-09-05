#!/usr/bin/env python3
"""Project the canonical Seymour blockchain catalog into Nexus format.

Canonical ownership remains with shared.provider_catalog.

The Nexus file is a deterministic packaged projection with Nexus-specific
presentation/planning fields. It is not an independent provider authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AVAILABILITY_ORDER = {
    "live": 0,
    "coming-soon": 1,
    "planned": 2,
    "disabled": 3,
}


def project_provider(provider: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(provider["providerId"])

    canonical_ports = provider.get("defaultPorts") or {}
    nexus_ports: dict[str, int] = {}

    if canonical_ports.get("p2p") is not None:
        nexus_ports["p2p"] = int(canonical_ports["p2p"])

    endpoint_port = canonical_ports.get("rpc")

    # Nexus currently models a provider's primary management/API endpoint
    # as "rpc". Ergo's canonical provider contract calls this "restApi".
    if endpoint_port is None:
        endpoint_port = canonical_ports.get("restApi")

    if endpoint_port is not None:
        nexus_ports["rpc"] = int(endpoint_port)

    disk = provider.get("estimatedDiskBytes")

    return {
        "providerId": provider_id,
        "coin": provider["ticker"],
        "name": provider["displayName"],
        "family": provider["family"],
        "network": provider["network"],
        "implementation": provider["implementation"],
        "availability": provider.get("availability", "planned"),
        "selectable": bool(provider.get("selectable", False)),
        # "enabled" means represented/enabled in the Nexus provider catalog.
        # It does NOT mean deployable. Deployment is governed by
        # availability + selectable.
        "enabled": provider.get("availability") != "disabled",
        "architectures": list(
            provider.get("supportedArchitectures") or []
        ),
        "defaultPorts": nexus_ports,
        "storage": {
            # Nexus deployment planning requires a deterministic default
            # directory identity even though the canonical provider catalog
            # does not own host-specific paths.
            "directoryName": provider_id,
            "minimumFreeBytes": (
                int(disk) if disk is not None else None
            ),
        },
    }


def project_catalog(canonical: dict[str, Any]) -> dict[str, Any]:
    providers = list(canonical.get("providers", []))

    # Nexus product presentation groups deployable providers first,
    # then Coming Soon providers, then Planned/Disabled providers.
    # Python's stable sort preserves canonical order within each group.
    providers.sort(
        key=lambda provider: AVAILABILITY_ORDER.get(
            str(provider.get("availability", "planned")),
            99,
        )
    )

    return {
        "schemaVersion": 1,
        "providers": [
            project_provider(provider)
            for provider in providers
        ],
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--target",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the packaged Nexus projection has drifted.",
    )

    args = parser.parse_args()

    canonical = load_json(args.source)
    projected = project_catalog(canonical)
    rendered = render_json(projected)

    if args.check:
        if not args.target.exists():
            print("projectionCheck=FAIL targetMissing")
            return 1

        current = args.target.read_text(encoding="utf-8")

        if current != rendered:
            print("projectionCheck=FAIL catalogDrift")
            return 1

        print("projectionCheck=PASS")
        print(
            "providerCount="
            + str(len(projected["providers"]))
        )
        return 0

    args.target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.target.write_text(
        rendered,
        encoding="utf-8",
    )

    print("projectionWrite=PASS")
    print(
        "providerCount="
        + str(len(projected["providers"]))
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
