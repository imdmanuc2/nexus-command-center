from backend.db.repositories.automation_repository import (
    automation_summary,
    list_actions,
    list_control_audit,
    list_runs,
)
from backend.services.automation_engine_service import (
    approve_automation,
    cancel_automation,
    process_queued_automations,
    reject_automation,
    request_automation,
)


def actions():
    items = list_actions()
    return {'status': 'ok', 'source': 'nexus-postgresql-platform-automation',
            'count': len(items), 'actions': items}


def runs():
    items = list_runs(100)
    return {'status': 'ok', 'source': 'nexus-postgresql-platform-automation',
            'count': len(items), 'runs': items}


def summary():
    return {'status': 'ok', 'source': 'nexus-postgresql-platform-automation',
            **automation_summary()}


def audit():
    items = list_control_audit(limit=100)
    return {'status': 'ok', 'source': 'nexus-postgresql-platform-automation',
            'count': len(items), 'audit': items}


def request(data):
    action_id = str(data.get('actionId', '')).strip()
    entity_type = str(data.get('entityType', 'platform')).strip()
    entity_id = str(data.get('entityId', 'primary')).strip()
    requested_by = str(data.get('requestedBy', 'operator')).strip() or 'operator'
    if not action_id:
        raise ValueError('Missing actionId')
    if not entity_type:
        raise ValueError('Missing entityType')
    if not entity_id:
        raise ValueError('Missing entityId')
    run = request_automation(
        action_id=action_id,
        entity_type=entity_type,
        entity_id=entity_id,
        recommendation_id=data.get('recommendationId'),
        requested_by=requested_by,
        dry_run=bool(data.get('dryRun', True)),
        input_payload=data.get('inputPayload') or {},
    )
    return {'status': 'ok', 'source': 'nexus-postgresql-platform-automation', 'run': run}


def approve(data):
    run_id = str(data.get('runId', '')).strip()
    if not run_id:
        raise ValueError('Missing runId')
    return {'status': 'ok', 'run': approve_automation(
        run_id=run_id,
        approved_by=str(data.get('approvedBy', 'operator')).strip() or 'operator',
        message=str(data.get('message', '')).strip(),
    )}


def reject(data):
    run_id = str(data.get('runId', '')).strip()
    if not run_id:
        raise ValueError('Missing runId')
    return {'status': 'ok', 'run': reject_automation(
        run_id=run_id,
        rejected_by=str(data.get('rejectedBy', 'operator')).strip() or 'operator',
        message=str(data.get('message', '')).strip(),
    )}


def cancel(data):
    run_id = str(data.get('runId', '')).strip()
    if not run_id:
        raise ValueError('Missing runId')
    return {'status': 'ok', 'run': cancel_automation(
        run_id=run_id,
        cancelled_by=str(data.get('cancelledBy', 'operator')).strip() or 'operator',
        message=str(data.get('message', '')).strip(),
    )}


def process(data):
    return process_queued_automations(
        limit=max(1, min(int(data.get('limit', 25)), 100))
    )
