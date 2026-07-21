from __future__ import annotations

from typing import Any

from backend.db.repositories.alert_repository import (
    get_alert_engine_state,
    list_enabled_rules,
    list_events_after,
    open_or_update_alert,
    resolve_alerts_for_entity,
    update_alert_engine_state,
)


SEVERITY_RANK = {
    "info": 10,
    "warning": 20,
    "critical": 30,
}


def _rule_matches(rule: dict[str, Any], event: dict[str, Any]) -> bool:
    if rule["event_type"] != event["event_type"]:
        return False

    if rule["entity_type"] not in ("*", event["entity_type"]):
        return False

    return (
        SEVERITY_RANK.get(event["severity"], 0)
        >= SEVERITY_RANK.get(rule["minimum_severity"], 0)
    )


def evaluate_alerts() -> dict[str, Any]:
    state = get_alert_engine_state()
    last_event_id = int(state.get("last_event_id") or 0)
    rules = list_enabled_rules()
    events = list_events_after(last_event_id)

    opened = 0
    updated = 0
    resolved = 0
    highest_event_id = last_event_id

    for event in events:
        highest_event_id = max(highest_event_id, event["event_id"])

        if event["event_type"] == "resource.online":
            resolved += resolve_alerts_for_entity(
                entity_type=event["entity_type"],
                entity_id=event["entity_id"],
            )
            continue

        for rule in rules:
            if not _rule_matches(rule, event):
                continue

            result = open_or_update_alert(
                rule_id=rule["rule_id"],
                event_id=event["event_id"],
                entity_type=event["entity_type"],
                entity_id=event["entity_id"],
                severity=event["severity"],
                title=event["title"],
                message=event["message"],
                metadata={
                    "eventType": event["event_type"],
                    "occurredAt": event["occurred_at"].isoformat(),
                },
            )

            if result == "opened":
                opened += 1
            else:
                updated += 1

    update_alert_engine_state(
        last_event_id=highest_event_id,
        status="ok",
        evaluated_events=len(events),
        alerts_opened=opened,
        alerts_updated=updated,
        alerts_resolved=resolved,
    )

    return {
        "status": "ok",
        "source": "nexus-platform-alert-engine",
        "evaluatedEvents": len(events),
        "alertsOpened": opened,
        "alertsUpdated": updated,
        "alertsResolved": resolved,
        "lastEventId": highest_event_id,
    }
