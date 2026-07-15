import json
from backend.services.platform_event_service import evaluate_platform_state


def main() -> int:
    print(json.dumps(evaluate_platform_state(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
