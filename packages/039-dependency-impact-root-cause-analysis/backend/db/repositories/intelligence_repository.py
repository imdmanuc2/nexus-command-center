from backend.db.connection import get_connection

def rows(sql, args=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]

def relationships():
    return rows("SELECT * FROM nexus.relationships WHERE status='active' AND approved=TRUE")

def asset(asset_id):
    result = rows("SELECT * FROM nexus.assets WHERE asset_id=%s", (asset_id,))
    return result[0] if result else {"asset_id": asset_id, "name": asset_id, "status": "unknown"}

def knowledge(asset_type=None, issue_code=None):
    clauses = ["active=TRUE"]
    args = []
    if asset_type:
        clauses.append("asset_type IN (%s,'compute','generic')")
        args.append(asset_type)
    if issue_code:
        clauses.append("issue_code=%s")
        args.append(issue_code)
    return rows(f"SELECT * FROM nexus.engineering_knowledge WHERE {' AND '.join(clauses)} ORDER BY base_confidence DESC", tuple(args))
