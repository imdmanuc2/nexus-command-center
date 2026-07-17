import json
from backend.services.identity_reconciliation_service import verify_identity_integrity
if __name__=='__main__': print(json.dumps(verify_identity_integrity(),indent=2))
