from backend.db.repositories.operational_state_repository import VALID_STATES, SUPPRESSED_STATES

def test_states():
    assert "active" in VALID_STATES
    assert {"maintenance","disabled","retired"} <= SUPPRESSED_STATES
