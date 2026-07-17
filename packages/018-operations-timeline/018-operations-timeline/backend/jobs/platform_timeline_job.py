import json
from backend.services.timeline_service import build_timeline

def main():
    print(json.dumps(build_timeline(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
