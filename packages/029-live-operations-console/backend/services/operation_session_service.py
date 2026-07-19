from __future__ import annotations

from backend.db.repositories.operation_session_repository import (
    append_event, ensure_session, get_session, get_session_by_run,
    list_events, list_sessions,
)


def create_for_run(run):
    session = ensure_session(run)
    if not list_events(session["sessionId"], limit=1):
        append_event(session_id=session["sessionId"], event_type="status",
                     stage="queued", message="Operation queued.",
                     progress_percent=0, session_status=run["status"])
    return get_session(session["sessionId"])


def emit(run, *, event_type, stage, message, progress=None,
         level="info", details=None, status=None, summary=None):
    session = get_session_by_run(run["runId"]) or create_for_run(run)
    return append_event(session_id=session["sessionId"], event_type=event_type,
                        stage=stage, message=message,
                        progress_percent=progress, level=level,
                        details=details, session_status=status, summary=summary)


def session_payload(*, run_id=None, session_id=None, after_event_id=0):
    session = get_session_by_run(run_id) if run_id else get_session(session_id)
    if session is None:
        raise ValueError("Unknown operation session")
    events = list_events(session["sessionId"], after_event_id=after_event_id)
    return {"status": "ok", "source": "nexus-live-operations-console",
            "session": session, "events": events,
            "lastEventId": events[-1]["eventId"] if events else int(after_event_id or 0)}


def sessions_payload(limit=100):
    items = list_sessions(limit)
    return {"status": "ok", "source": "nexus-live-operations-console",
            "count": len(items), "sessions": items}
