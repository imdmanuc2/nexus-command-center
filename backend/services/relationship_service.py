"""PostgreSQL relationship service with canonical CMDB object resolution."""
from backend.db.repositories.relationship_repository import list_relationships
from backend.services.cmdb_object_service import resolve_object


def relationships():
    records = list_relationships()
    by_type = {}
    resolved_records = []

    for record in records:
        relationship_type = record.get("relationshipType") or "unknown"
        by_type[relationship_type] = by_type.get(relationship_type, 0) + 1

        source = resolve_object(
            str(record.get("sourceId") or ""),
            str(record.get("sourceType") or "object"),
        )
        target = resolve_object(
            str(record.get("targetId") or ""),
            str(record.get("targetType") or "object"),
        )
        resolved_records.append({
            **record,
            "sourceName": source["displayName"],
            "sourceHref": source["href"],
            "sourceObject": source,
            "targetName": target["displayName"],
            "targetHref": target["href"],
            "targetObject": target,
        })

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "count": len(resolved_records),
        "byType": by_type,
        "relationships": resolved_records,
    }
