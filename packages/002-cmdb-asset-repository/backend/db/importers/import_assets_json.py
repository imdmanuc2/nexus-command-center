"""Repeat-safe importer from legacy assets.json into PostgreSQL."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

from backend.db.repositories.asset_repository import bulk_upsert_assets, count_assets

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FILE = PROJECT_ROOT / "backend/data/assets.json"

def load_assets(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        if isinstance(raw.get("assets"), list):
            return [item for item in raw["assets"] if isinstance(item, dict)]
        return [item for item in raw.values() if isinstance(item, dict)]
    raise ValueError("assets.json must contain a JSON list or object.")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"Asset source file not found: {args.file}")

    assets = load_assets(args.file)
    print(f"Source file: {args.file}")
    print(f"Source assets: {len(assets)}")
    for asset in assets:
        print(
            asset.get("id"),
            asset.get("assetType") or asset.get("type") or "unknown",
            asset.get("friendlyName") or asset.get("name") or asset.get("ip"),
        )

    if args.dry_run:
        print("Dry run complete. PostgreSQL unchanged.")
        return 0

    imported = bulk_upsert_assets(assets)
    database_count = count_assets()
    print()
    print(f"Imported this run: {len(imported)}")
    print(f"Database assets:  {database_count}")
    if database_count < len(assets):
        raise SystemExit("Import verification failed: database count is too low.")
    print("Asset import verified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
