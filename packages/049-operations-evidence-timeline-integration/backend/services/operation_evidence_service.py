from __future__ import annotations

from backend.db.repositories import operation_evidence_repository as repo

WORKER_NAME = 'nexus-operation-evidence-worker'


def pick(row, *names):
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return None


def text(value):
    return None if value is None else str(value)


def severity(status):
    status = (status or '').lower()
    if status in {'failed', 'error', 'rollback-required'}:
        return 'critical'
    if status in {'warning', 'partial', 'queued', 'running', 'pending'}:
        return 'warning'
    return 'info'


def record(source_type, source_id, operation_type, operation_name, status, summary, row, score=None):
    return {
        'source_type': source_type,
        'source_id': str(source_id),
        'correlation_id': text(pick(row, 'correlation_id', 'correlationId')),
        'change_request_id': text(pick(row, 'change_request_id', 'change_id')),
        'asset_id': text(pick(row, 'asset_id', 'target_asset_id', 'target_id')),
        'service_id': text(pick(row, 'service_id', 'target_service_id')),
        'operation_type': operation_type,
        'operation_name': operation_name,
        'actor_type': text(pick(row, 'actor_type')) or 'system',
        'actor_id': text(pick(row, 'actor_id', 'requested_by', 'created_by')),
        'status': status,
        'severity': severity(status),
        'summary': summary,
        'score': score,
        'started_at': pick(row, 'started_at', 'created_at', 'requested_at'),
        'completed_at': pick(row, 'completed_at', 'finished_at', 'updated_at'),
        'evidence': row,
        'metadata': {'aggregatedBy': WORKER_NAME},
    }


def aggregate_once():
    repo.worker_started(WORKER_NAME)
    counts = {'changeExecutions': 0, 'verifications': 0, 'rollbacks': 0}
    try:
        with repo.connection() as conn:
            executions = repo.source_rows(conn, 'change_execution_attempts',
                'SELECT * FROM change_execution_attempts ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT 500')
            verifications = repo.source_rows(conn, 'verification_runs',
                'SELECT * FROM verification_runs ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT 500')
            rollbacks = repo.source_rows(conn, 'change_rollbacks',
                'SELECT * FROM change_rollbacks ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT 500')

        for row in executions:
            source_id = pick(row, 'attempt_id', 'execution_id', 'id')
            status = text(pick(row, 'status')) or 'unknown'
            name = text(pick(row, 'capability', 'operation', 'action')) or 'change execution'
            repo.upsert(record('change-execution', source_id, 'execution', name, status,
                               f'Change execution {name}: {status}', row))
            counts['changeExecutions'] += 1

        for row in verifications:
            source_id = pick(row, 'run_id', 'verification_run_id', 'id')
            status = text(pick(row, 'status', 'verification_status')) or 'unknown'
            name = text(pick(row, 'profile_key', 'profile_id')) or 'verification'
            repo.upsert(record('verification-run', source_id, 'verification', name, status,
                               f'Verification {name}: {status}', row,
                               pick(row, 'score', 'verification_score')))
            counts['verifications'] += 1

        for row in rollbacks:
            source_id = pick(row, 'rollback_id', 'id')
            status = text(pick(row, 'status')) or 'unknown'
            name = text(pick(row, 'capability', 'operation')) or 'change rollback'
            repo.upsert(record('change-rollback', source_id, 'rollback', name, status,
                               f'Rollback {name}: {status}', row))
            counts['rollbacks'] += 1

        result = {'status': 'ok', 'counts': counts, 'total': sum(counts.values())}
        repo.worker_finished(WORKER_NAME, result)
        return result
    except Exception as exc:
        repo.worker_finished(WORKER_NAME, {'status': 'error', 'counts': counts}, str(exc))
        raise


def list_evidence(query=None):
    query = query or {}
    rows = repo.list_evidence(
        int((query.get('limit') or ['100'])[0]),
        (query.get('assetId') or [None])[0],
        (query.get('status') or [None])[0],
        (query.get('operationType') or [None])[0],
        (query.get('correlationId') or [None])[0],
    )
    return {'status': 'ok', 'count': len(rows), 'evidence': rows}


def get_evidence(evidence_id):
    row = repo.get_evidence(evidence_id)
    return {'status': 'ok', 'evidence': row} if row else {'status': 'not-found', 'error': 'Evidence record not found'}


def asset_operations(asset_id, query=None):
    query = query or {}
    rows = repo.list_evidence(int((query.get('limit') or ['100'])[0]), asset_id=asset_id)
    return {'status': 'ok', 'assetId': asset_id, 'count': len(rows), 'operations': rows}


def timeline(query=None):
    result = list_evidence(query)
    return {'status': 'ok', 'count': result['count'], 'timeline': result['evidence'], 'source': 'nexus-operation-evidence'}


def recommendation_context(query=None):
    query = query or {}
    rows = repo.list_evidence(int((query.get('limit') or ['100'])[0]))
    failures = [r for r in rows if r.get('status') in {'failed', 'error', 'rollback-required'}]
    rollbacks = [r for r in rows if r.get('operation_type') == 'rollback']
    return {'status': 'ok', 'context': {
        'recentOperations': rows,
        'failedOperations': failures,
        'recentRollbacks': rollbacks,
        'confidenceBasis': {'evidenceCount': len(rows), 'failureCount': len(failures), 'rollbackCount': len(rollbacks)},
    }}


def status(_query=None):
    return {'status': 'ok', 'source': WORKER_NAME, 'worker': repo.worker_status(WORKER_NAME)}
