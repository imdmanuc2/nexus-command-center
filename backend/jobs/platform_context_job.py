import json

from backend.services.platform_context_service import build_contexts


def main() -> int:
    print(json.dumps(build_contexts(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
