import json
from backend.services.automation_engine_service import process_queued_automations

def main(): print(json.dumps(process_queued_automations(),indent=2));return 0
if __name__=='__main__': raise SystemExit(main())
