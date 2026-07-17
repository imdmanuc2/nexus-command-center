from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from backend.db.connection import get_connection
from backend.db.repositories.timeline_repository import (
    append, remember, save_state, state
)

def rows(sql, params=()):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def build_timeline():
    s = state()
    event_id = int(s.get("last_platform_event_id") or 0)
    alert_at = s.get("last_alert_seen_at")
    rec_at = s.get("last_recommendation_seen_at")
    auto_at = s.get("last_automation_seen_at")
    written = 0
    try:
        for e in rows(
            "SELECT * FROM nexus.platform_events WHERE event_id>%s ORDER BY event_id",
            (event_id,)
        ):
            written += int(append(
                source_type="platform-event", source_id=str(e["event_id"]),
                event_type=e["event_type"], severity=e["severity"],
                entity_type=e["entity_type"], entity_id=e["entity_id"],
                title=e["title"], message=e["message"],
                data={"previousState": e["previous_state"] or {},
                      "currentState": e["current_state"] or {}},
                occurred_at=e["occurred_at"]
            ))
            if e["current_state"]:
                raw = json.dumps(e["current_state"], sort_keys=True, default=str)
                remember(
                    entity_type=e["entity_type"], entity_id=e["entity_id"],
                    payload=e["current_state"],
                    state_hash=hashlib.sha256(raw.encode()).hexdigest(),
                    observed_at=e["occurred_at"]
                )
            event_id = max(event_id, e["event_id"])

        for a in rows("""
            SELECT * FROM nexus.alerts
            WHERE last_seen_at>COALESCE(%s,'1970-01-01'::timestamptz)
            ORDER BY last_seen_at
        """, (alert_at,)):
            data = a["data"] or {}
            sid = f"{a['alert_id']}:{a['status']}:{a['last_seen_at'].isoformat()}"
            written += int(append(
                source_type="alert", source_id=sid,
                event_type=f"alert.{a['status']}", severity=a["severity"],
                entity_type=str(data.get("entityType") or ""),
                entity_id=str(data.get("entityId") or ""),
                title=a["title"], message=a["message"],
                data={"alertId": a["alert_id"], "priority": a["priority"],
                      "recommendedAction": a["recommended_action"]},
                occurred_at=a["last_seen_at"]
            ))
            alert_at = a["last_seen_at"]

        for r in rows("""
            SELECT * FROM nexus.recommendations
            WHERE last_generated_at>COALESCE(%s,'1970-01-01'::timestamptz)
            ORDER BY last_generated_at
        """, (rec_at,)):
            sid = f"{r['recommendation_id']}:{r['status']}:{r['last_generated_at'].isoformat()}"
            sev = "critical" if r["priority"]=="critical" else "warning" if r["priority"]=="high" else "info"
            written += int(append(
                source_type="recommendation", source_id=sid,
                event_type=f"recommendation.{r['status']}", severity=sev,
                entity_type=r["entity_type"], entity_id=r["entity_id"],
                title=r["title"], message=r["explanation"],
                data={"recommendationId": r["recommendation_id"],
                      "recommendedAction": r["recommended_action"],
                      "confidence": r["confidence"]},
                occurred_at=r["last_generated_at"]
            ))
            rec_at = r["last_generated_at"]

        for run in rows("""
            SELECT * FROM nexus.automation_runs
            WHERE updated_at>COALESCE(%s,'1970-01-01'::timestamptz)
            ORDER BY updated_at
        """, (auto_at,)):
            sid = f"{run['run_id']}:{run['status']}:{run['updated_at'].isoformat()}"
            written += int(append(
                source_type="automation", source_id=sid,
                event_type=f"automation.{run['status']}",
                severity="critical" if run["status"]=="failed" else "info",
                entity_type=run["entity_type"], entity_id=run["entity_id"],
                title=f"Automation {run['status']}",
                message=run["error_message"] or f"Action {run['action_id']} is {run['status']}.",
                data={"runId": run["run_id"], "actionId": run["action_id"],
                      "dryRun": run["dry_run"], "result": run["result_payload"] or {}},
                occurred_at=run["updated_at"]
            ))
            auto_at = run["updated_at"]

        save_state(event_id=event_id, alert_at=alert_at, rec_at=rec_at,
                   automation_at=auto_at, status="ok", error="", written=written)
        return {
            "status": "ok", "source": "nexus-operations-timeline",
            "entriesWritten": written, "lastPlatformEventId": event_id,
            "completedAt": datetime.now(timezone.utc).isoformat()
        }
    except Exception as exc:
        save_state(event_id=event_id, alert_at=alert_at, rec_at=rec_at,
                   automation_at=auto_at, status="error",
                   error=str(exc), written=written)
        raise
