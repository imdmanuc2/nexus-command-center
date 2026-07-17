from backend.db.connection import get_connection
from backend.db.repositories.identity_reconciliation_repository import identity_summary

def verify_identity_integrity():
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute("""SELECT source_system,source_worker_id,COUNT(*) row_count FROM nexus.workers WHERE source_system<>'' AND source_worker_id<>'' GROUP BY source_system,source_worker_id HAVING COUNT(*)>1""");dups=cursor.fetchall()
        cursor.execute('SELECT COUNT(*) worker_count FROM nexus.workers');count=cursor.fetchone()['worker_count']
    return {'status':'ok' if not dups else 'error','source':'nexus-identity-reconciliation','workerCount':count,'duplicateWorkerIdentities':len(dups),'duplicates':[dict(r) for r in dups],'audit':identity_summary()}
