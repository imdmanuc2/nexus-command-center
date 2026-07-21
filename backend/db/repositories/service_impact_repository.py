from backend.db.connection import get_connection


def _rows(sql, args=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]


def active_relationships():
    return _rows("""
        SELECT relationship_id, source_id, target_id, relationship_type,
               criticality, redundancy_group, confidence, metadata
        FROM nexus.relationships
        WHERE status='active' AND approved=TRUE
        ORDER BY relationship_type, source_id, target_id
    """)


def assets(asset_ids):
    ids = list(dict.fromkeys(asset_ids))
    if not ids:
        return []
    return _rows("""
        SELECT asset_id, name, asset_type,
               COALESCE(operational_state, 'unknown') AS operational_state,
               lifecycle_status
        FROM nexus.assets
        WHERE asset_id = ANY(%s)
    """, (ids,))


def rules(service_id=None):
    where = "WHERE active=TRUE AND service_id=%s" if service_id else "WHERE active=TRUE"
    args = (service_id,) if service_id else ()
    return _rows(f"SELECT * FROM nexus.service_dependency_rules {where} ORDER BY service_id, rule_id", args)


def snapshots(service_id=None, limit=50):
    where = "WHERE service_id=%s" if service_id else ""
    args = (service_id, limit) if service_id else (limit,)
    return _rows(f"""
        SELECT * FROM nexus.service_impact_snapshots
        {where}
        ORDER BY observed_at DESC LIMIT %s
    """, args)
