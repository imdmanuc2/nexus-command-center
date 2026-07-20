from backend.services.policy_engine_service import decisions_payload, evaluate_payload, policies_payload

def policies(query=None): return policies_payload()
def decisions(query): return decisions_payload(int((query.get("limit") or ["100"])[0]))
def evaluate(data): return evaluate_payload(data)
