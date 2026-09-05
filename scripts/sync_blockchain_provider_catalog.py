#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_REPO = (
    REPO_ROOT.parent / "seymour-umbrel-app-store"
)

CANONICAL_RELATIVE_PATH = Path(
    "shared/provider_catalog/providers.v1.json"
)

TARGET = (
    REPO_ROOT
    / "backend/data/config/blockchain_provider_catalog.json"
)

PROJECTOR = (
    REPO_ROOT
    / "scripts/project_blockchain_provider_catalog.py"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize Nexus's packaged blockchain provider "
            "catalog from the canonical Seymour Umbrel App Store catalog."
        )
    )

    parser.add_argument(
        "--source-repo",
        type=Path,
        default=DEFAULT_SOURCE_REPO,
        help=(
            "Path to seymour-umbrel-app-store. "
            "Defaults to the sibling development checkout."
        ),
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for drift without writing the Nexus projection.",
    )

    args = parser.parse_args()

    source = (
        args.source_repo.expanduser().resolve()
        / CANONICAL_RELATIVE_PATH
    )

    if not source.is_file():
        print(
            "catalogSync=FAIL "
            f"canonicalCatalogNotFound={source}",
            file=sys.stderr,
        )
        return 2

    command = [
        sys.executable,
        str(PROJECTOR),
        "--source",
        str(source),
        "--target",
        str(TARGET),
    ]

    if args.check:
        command.append("--check")

    completed = subprocess.run(
        command,
        check=False,
    )

    if completed.returncode != 0:
        return completed.returncode

    print(
        "catalogOwner=seymour-umbrel-app-store:"
        "shared/provider_catalog/providers.v1.json"
    )
    print(
        "catalogProjection="
        "backend/data/config/blockchain_provider_catalog.json"
    )
    print(
        "catalogSyncMode="
        + ("check" if args.check else "write")
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
