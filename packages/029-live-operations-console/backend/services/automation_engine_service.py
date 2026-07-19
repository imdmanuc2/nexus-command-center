from __future__ import annotations

import contextlib
import io

from backend.db.repositories.automation_repository import (
    approve_run,
    cancel_run,
    complete_run,
    create_run,
    get_action,
    get_run,
    list_queued_runs,
    mark_run_running,
    reject_run,
)
from backend.jobs.platform_resource_sync import synchronize_platform_resources
from backend.executors.registry import get_executor_registry
from backend.services.operation_session_service import create_for_run, emit


def request_automation(*, action_id, entity_type, entity_id,
                       recommendation_id=None, requested_by='operator',
                       dry_run=True, input_payload=None):
    action = get_action(action_id)
    input_payload = input_payload or {}
    if {'command', 'shell', 'argv'} & set(input_payload):
        raise ValueError('Arbitrary command execution is prohibited')
    if action is None:
        raise ValueError(f'Unknown or disabled action: {action_id}')
    if action['entityType'] not in {'*', entity_type}:
        raise ValueError(f'Action {action_id} does not support {entity_type}')
    if dry_run and not action['supportsDryRun']:
        raise ValueError(f'Action {action_id} does not support dry-run')
    run = create_run(
        action_id=action_id,
        recommendation_id=recommendation_id,
        entity_type=entity_type,
        entity_id=entity_id,
        requested_by=requested_by,
        dry_run=dry_run,
        input_payload=input_payload,
        execution_plan={
            'action': action,
            'entityType': entity_type,
            'entityId': entity_id,
            'dryRun': dry_run,
        },
        requires_approval=action['requiresApproval'],
    )
    create_for_run(run)
    return run


def _transition(fn, *, run_id, actor_key, actor, message):
    run = fn(run_id=run_id, **{actor_key: actor}, message=message)
    if run is not None:
        return run
    existing = get_run(run_id)
    if existing is None:
        raise ValueError(f'Unknown automation run: {run_id}')
    raise ValueError(
        f"Run {run_id} cannot transition from status {existing['status']}"
    )


def approve_automation(*, run_id, approved_by='operator', message=''):
    return _transition(
        approve_run,
        run_id=run_id,
        actor_key='approved_by',
        actor=approved_by,
        message=message,
    )


def reject_automation(*, run_id, rejected_by='operator', message=''):
    return _transition(
        reject_run,
        run_id=run_id,
        actor_key='rejected_by',
        actor=rejected_by,
        message=message,
    )


def cancel_automation(*, run_id, cancelled_by='operator', message=''):
    return _transition(
        cancel_run,
        run_id=run_id,
        actor_key='cancelled_by',
        actor=cancelled_by,
        message=message,
    )


def _execute(run):
    if run['dryRun']:
        return {
            'status': 'dry-run-complete',
            'dryRun': True,
            'wouldExecute': run['actionId'],
            'entityType': run['entityType'],
            'entityId': run['entityId'],
            'inputPayload': run['inputPayload'],
        }
    if run['actionId'] == 'refresh-platform-sync':
        from backend.jobs.platform_sync_job import run_once
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            return run_once(stale_seconds=300, dry_run=False)
    if run['actionId'] == 'refresh-resource-sync':
        return synchronize_platform_resources(stale_seconds=300)

    registry = get_executor_registry()
    executor = registry.resolve(run['actionId'], run)
    if executor is None:
        return {
            'status': 'planned',
            'safeNoop': True,
            'message': (
                'This action is cataloged and audited, but no managed '
                'executor is registered. No remote command was executed.'
            ),
        }

    result = executor.execute(run).to_dict()
    if result.get('status') == 'failed':
        raise RuntimeError(result.get('summary') or 'Managed execution failed.')
    return result


def process_queued_automations(limit=25):
    queued = list_queued_runs(limit)
    completed = failed = 0
    results = []
    for run in queued:
        create_for_run(run)
        if not mark_run_running(run['runId']):
            continue
        try:
            emit(run, event_type='status', stage='connecting', message='Preparing managed execution.', progress=10, status='running')
            emit(run, event_type='progress', stage='authorization', message='Approval and capability policy verified.', progress=25)
            emit(run, event_type='status', stage='executing', message=f"Executing {run['actionId']}.", progress=45)
            result = _execute(run)
            emit(run, event_type='verification', stage='verifying', message='Post-action verification completed.', progress=80, details={'resultStatus': result.get('status')})
            complete_run(run_id=run['runId'], status='completed', result_payload=result)
            emit(run, event_type='complete', stage='completed', message='Operation completed successfully.', progress=100, status='completed', summary=result.get('summary') or 'Operation completed.', details=result)
            completed += 1
            results.append({'runId': run['runId'], 'status': 'completed', 'result': result})
        except Exception as exc:
            complete_run(run_id=run['runId'], status='failed', result_payload={}, error_message=str(exc))
            emit(run, event_type='error', stage='failed', message=str(exc), progress=100, level='error', status='failed', summary=str(exc))
            failed += 1
            results.append({'runId': run['runId'], 'status': 'failed', 'error': str(exc)})
    return {
        'status': 'ok',
        'source': 'nexus-operations-automation-engine',
        'queuedRuns': len(queued),
        'completedRuns': completed,
        'failedRuns': failed,
        'results': results,
    }
