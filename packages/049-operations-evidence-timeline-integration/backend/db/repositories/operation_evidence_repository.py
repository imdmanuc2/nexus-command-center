from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _kwargs():
    url = os.getenv('DATABASE_URL') or os.getenv('NEXUS_DATABASE_URL')
    if url:
        return {'conninfo': url}
    return {
        'host': os.getenv('NEXUS_DB_HOST', 'localhost'),
        'port': int(os.getenv('NEXUS_DB_PORT', '5432')),
        'dbname': os.getenv('NEXUS_DB_NAME', 'nexus_platform'),
        'user': os.getenv('NEXUS_DB_USER', 'nexus_app'),
        'password': os.getenv('NEXUS_DB_PASSWORD', ''),
    }


@contextmanager
def connection():
    kw = _kwargs()
    conn = psycopg.connect(kw.pop('conninfo'), row_factory=dict_row) if 'conninfo' in kw else psycopg.connect(**kw, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def table_exists(conn, name):
    with conn.cursor() as cur:
        cur.execute('SELECT to_regclass(%s) IS NOT NULL AS present', (name,))
        return bool(cur.fetchone()['present'])


def source_rows(conn, name, sql):
    if not table_exists(conn, name):
        return []
    with conn.cursor() as cur:
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]


def upsert(record):
    record = dict(record)
    record['evidence_json'] = json.dumps(record.get('evidence') or {}, default=str)
    record['metadata_json'] = json.dumps(record.get('metadata') or {}, default=str)
    with connection() as conn, conn.cursor() as cur:
        cur.execute('''
            INSERT INTO operation_evidence(
                source_type,source_id,correlation_id,change_request_id,asset_id,service_id,
                operation_type,operation_name,actor_type,actor_id,status,severity,summary,score,
                started_at,completed_at,evidence,metadata,first_observed_at,last_observed_at,updated_at
            ) VALUES (
                %(source_type)s,%(source_id)s,%(correlation_id)s,%(change_request_id)s,%(asset_id)s,%(service_id)s,
                %(operation_type)s,%(operation_name)s,%(actor_type)s,%(actor_id)s,%(status)s,%(severity)s,%(summary)s,%(score)s,
                %(started_at)s,%(completed_at)s,%(evidence_json)s::jsonb,%(metadata_json)s::jsonb,
                COALESCE(%(started_at)s,NOW()),NOW(),NOW()
            )
            ON CONFLICT(source_type,source_id) DO UPDATE SET
                correlation_id=COALESCE(EXCLUDED.correlation_id,operation_evidence.correlation_id),
                change_request_id=COALESCE(EXCLUDED.change_request_id,operation_evidence.change_request_id),
                asset_id=COALESCE(EXCLUDED.asset_id,operation_evidence.asset_id),
                service_id=COALESCE(EXCLUDED.service_id,operation_evidence.service_id),
                operation_type=EXCLUDED.operation_type,operation_name=EXCLUDED.operation_name,
                actor_type=EXCLUDED.actor_type,actor_id=COALESCE(EXCLUDED.actor_id,operation_evidence.actor_id),
                status=EXCLUDED.status,severity=EXCLUDED.severity,summary=EXCLUDED.summary,
                score=COALESCE(EXCLUDED.score,operation_evidence.score),
                started_at=COALESCE(EXCLUDED.started_at,operation_evidence.started_at),
                completed_at=COALESCE(EXCLUDED.completed_at,operation_evidence.completed_at),
                evidence=EXCLUDED.evidence,metadata=operation_evidence.metadata || EXCLUDED.metadata,
                last_observed_at=NOW(),updated_at=NOW()
            RETURNING *
        ''', record)
        return dict(cur.fetchone())


def list_evidence(limit=100, asset_id=None, status=None, operation_type=None, correlation_id=None):
    clauses, params = [], []
    for column, value in [('asset_id', asset_id), ('status', status), ('operation_type', operation_type), ('correlation_id', correlation_id)]:
        if value:
            clauses.append(f'{column}=%s')
            params.append(value)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    params.append(max(1, min(int(limit), 500)))
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f'''SELECT * FROM operation_evidence {where}
                       ORDER BY COALESCE(completed_at,started_at,created_at) DESC LIMIT %s''', params)
        return [dict(row) for row in cur.fetchall()]


def get_evidence(evidence_id):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM operation_evidence WHERE evidence_id=%s::uuid', (evidence_id,))
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        cur.execute('SELECT * FROM operation_evidence_events WHERE evidence_id=%s::uuid ORDER BY occurred_at', (evidence_id,))
        result['events'] = [dict(x) for x in cur.fetchall()]
        cur.execute('SELECT * FROM operation_annotations WHERE evidence_id=%s::uuid ORDER BY created_at', (evidence_id,))
        result['annotations'] = [dict(x) for x in cur.fetchall()]
        return result


def worker_started(name):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO operation_evidence_worker_state(worker_name,last_started_at,updated_at)
                       VALUES(%s,NOW(),NOW()) ON CONFLICT(worker_name) DO UPDATE SET last_started_at=NOW(),updated_at=NOW()''', (name,))


def worker_finished(name, result, error=None):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO operation_evidence_worker_state(
                         worker_name,last_completed_at,last_success_at,last_error_at,last_error,last_result,updated_at)
                       VALUES(%s,NOW(),CASE WHEN %s::text IS NULL THEN NOW() END,CASE WHEN %s::text IS NOT NULL THEN NOW() END,%s,%s::jsonb,NOW())
                       ON CONFLICT(worker_name) DO UPDATE SET
                         last_completed_at=NOW(),
                         last_success_at=CASE WHEN EXCLUDED.last_error IS NULL THEN NOW() ELSE operation_evidence_worker_state.last_success_at END,
                         last_error_at=CASE WHEN EXCLUDED.last_error IS NOT NULL THEN NOW() ELSE operation_evidence_worker_state.last_error_at END,
                         last_error=EXCLUDED.last_error,last_result=EXCLUDED.last_result,updated_at=NOW()''',
                    (name, error, error, error, json.dumps(result, default=str)))


def worker_status(name):
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM operation_evidence_worker_state WHERE worker_name=%s', (name,))
        row = cur.fetchone()
        return dict(row) if row else None
