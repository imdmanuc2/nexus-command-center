from backend.services.operation_session_service import session_payload, sessions_payload


def sessions(query=None):
    query = query or {}
    return sessions_payload(limit=int(query.get("limit", [100])[0]))


def session(query=None):
    query = query or {}
    run_id = query.get("runId", [None])[0]
    session_id = query.get("sessionId", [None])[0]
    after = int(query.get("afterEventId", [0])[0])
    if not run_id and not session_id:
        raise ValueError("Missing runId or sessionId")
    return session_payload(run_id=run_id, session_id=session_id, after_event_id=after)
