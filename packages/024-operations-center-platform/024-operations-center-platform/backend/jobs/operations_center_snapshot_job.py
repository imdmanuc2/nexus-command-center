
import json

from backend.db.repositories.operations_center_repository import (
    prune_operations_snapshots,
)
from backend.services.operations_center_service import (
    build_operations_center,
)


def main() -> int:
    result = build_operations_center(
        persist=True,
    )
    result["snapshotsPruned"] = (
        prune_operations_snapshots(
            keep_days=30,
        )
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
