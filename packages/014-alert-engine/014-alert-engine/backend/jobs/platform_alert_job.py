import json
from backend.services.alert_engine_service import evaluate_alerts


def main() -> int:
    print(json.dumps(evaluate_alerts(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
