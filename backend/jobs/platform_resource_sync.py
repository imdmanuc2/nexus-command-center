import json
from backend.services.blockchain_sync_service import synchronize_blockchain_nodes
from backend.services.miningcore_sync_service import synchronize_miningcore_instances
def synchronize_platform_resources(stale_seconds=300):return {'status':'ok','blockchain':synchronize_blockchain_nodes(stale_seconds),'miningcore':synchronize_miningcore_instances(stale_seconds)}
def main():print(json.dumps(synchronize_platform_resources(),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
