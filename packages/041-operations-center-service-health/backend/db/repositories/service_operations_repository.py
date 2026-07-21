from backend.db.connection import get_connection


def _rows(sql, args=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]


def open_incidents():
    return _rows("""
        SELECT i.*, s.name AS service_name, s.criticality
        FROM nexus.service_incidents i
        JOIN nexus.business_services s ON s.service_id=i.service_id
        WHERE i.status IN ('open','acknowledged')
        ORDER BY CASE i.severity WHEN 'critical' THEN 1 WHEN 'degraded' THEN 2 WHEN 'warning' THEN 3 ELSE 4 END,
                 i.opened_at DESC
    """)


def recent_snapshots(limit=100):
    return _rows("""
        SELECT h.*, s.name AS service_name
        FROM nexus.service_health_snapshots h
        JOIN nexus.business_services s ON s.service_id=h.service_id
        ORDER BY h.observed_at DESC LIMIT %s
    """, (limit,))
