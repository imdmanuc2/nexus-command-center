import json

from backend.services.recommendation_engine_service import (
    evaluate_recommendations,
)


def main() -> int:
    print(json.dumps(evaluate_recommendations(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
