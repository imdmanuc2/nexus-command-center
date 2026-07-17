
import json

from backend.services.worker_activity_reconciliation_service import (
    reconcile_worker_activity,
)


def main() -> int:
    print(json.dumps(reconcile_worker_activity(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
