from backend.services.deployment_service import transition_payload

def test_module_imports():
    assert callable(transition_payload)
