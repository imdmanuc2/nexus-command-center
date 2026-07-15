import json, logging
from backend.services.telemetry_collector_service import collect_and_store
from backend.db.repositories.telemetry_repository import build_rollups,apply_retention
def main():
    logging.basicConfig(level=logging.INFO)
    try:
        count=collect_and_store()
        rollups={s:build_rollups(s) for s in ("1m","1h","1d")}
        print(json.dumps({"status":"ok","sampleCount":count,"rollups":rollups,
                          "retention":apply_retention()},indent=2))
        return 0
    except Exception:
        logging.exception("Telemetry collection failed")
        return 1
if __name__=="__main__":
    raise SystemExit(main())
