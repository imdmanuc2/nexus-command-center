
import json

from backend.services.topology_reconciliation_service import (
    reconcile_live_topology,
)


def main() -> int:
    print(json.dumps(reconcile_live_topology(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
