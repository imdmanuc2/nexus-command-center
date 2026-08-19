from __future__ import annotations

from typing import Any

from backend.services.maintenance_service import should_suppress_alert

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

    suppression_cache: dict[tuple[str, str], bool] = {}

    for event in events:
        highest_event_id = max(highest_event_id, event["event_id"])

        entity_type = event["entity_type"]
        entity_id = event["entity_id"]

        # Recovery events should clear active alerts regardless of whether
        # the entity is currently covered by a maintenance window.
        if event["event_type"] == "resource.online":
            resolved += resolve_alerts_for_entity(
                entity_type=entity_type,
                entity_id=entity_id,
            )
            continue

        # Most platform events are routine telemetry/state changes. Do not
        # perform maintenance lookups unless an enabled alert rule actually
        # cares about this event.
        matching_rules = [
            rule
            for rule in rules
            if _rule_matches(rule, event)
        ]

        if not matching_rules:
            continue

        # Maintenance state is stable for the duration of one alert-engine
        # pass. Cache it per entity instead of opening a PostgreSQL
        # connection for every historical event.
        suppression_key = (entity_type, entity_id)

        if suppression_key not in suppression_cache:
            suppression_cache[suppression_key] = should_suppress_alert(
                entity_type,
                entity_id,
            )

        if suppression_cache[suppression_key]:
            continue

        for rule in matching_rules:
            result = open_or_update_alert(
                rule_id=rule["rule_id"],
                event_id=event["event_id"],
                entity_type=entity_type,
                entity_id=entity_id,
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
            elif result in ("updated", "reopened"):
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
