from backend.db.connection import get_connection


def _rows(sql, args=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]


def services():
    return _rows("SELECT * FROM nexus.business_services ORDER BY criticality DESC, name")


def service(service_id):
    rows = _rows("SELECT * FROM nexus.business_services WHERE service_id=%s", (service_id,))
    return rows[0] if rows else None


def members(service_id=None):
    where = "WHERE m.service_id=%s" if service_id else ""
    args = (service_id,) if service_id else ()

    return _rows(
        f"""
        SELECT
            m.*,
            a.name AS asset_name,
            a.asset_type,
            COALESCE(a.operational_state, 'active') AS asset_operational_state,
            net.ip_address
        FROM nexus.business_service_members m
        JOIN nexus.assets a
          ON a.asset_id = m.asset_id
        LEFT JOIN LATERAL (
            SELECT n.address AS ip_address
            FROM nexus.asset_network_addresses n
            WHERE n.asset_id = a.asset_id
              AND n.is_active = TRUE
              AND n.retired_at IS NULL
            ORDER BY
                CASE WHEN n.is_primary THEN 0 ELSE 1 END,
                n.last_seen_at DESC NULLS LAST,
                n.address_id DESC
            LIMIT 1
        ) net ON TRUE
        {where}
        ORDER BY m.required DESC, m.role, a.name
        """,
        args,
    )


def dependencies(service_id=None):
    where = "WHERE d.service_id=%s" if service_id else ""
    args = (service_id,) if service_id else ()
    return _rows(f"""
        SELECT d.*, s.name AS service_name, p.name AS depends_on_service_name
        FROM nexus.business_service_dependencies d
        JOIN nexus.business_services s ON s.service_id=d.service_id
        JOIN nexus.business_services p ON p.service_id=d.depends_on_service_id
        {where}
        ORDER BY s.name, p.name
    """, args)


def workload_counts(service_id):
    return _rows("""
        SELECT w.workload_category, count(*)::int AS count
        FROM nexus.business_service_members m
        JOIN nexus.workload_assignments w ON w.asset_id=m.asset_id AND w.status IN ('assigned','active','running')
        WHERE m.service_id=%s
        GROUP BY w.workload_category ORDER BY w.workload_category
    """, (service_id,))
