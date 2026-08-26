"""API-facing Nexus instance identity read model."""

from backend.db.repositories.nexus_instance_repository import (
    get_nexus_instance,
    list_nexus_instances,
)


def _instance_payload(row):
    return {
        "instanceId": row.get("instance_id"),
        "organizationId": row.get("organization_id"),
        "organizationName": row.get("organization_name"),
        "siteId": row.get("site_id"),
        "siteName": row.get("site_name"),
        "name": row.get("name"),
        "hostname": row.get("hostname"),
        "instanceRole": row.get("instance_role"),
        "status": row.get("status"),
        "isLocal": bool(row.get("is_local")),
        "federationEnabled": bool(
            row.get("federation_enabled")
        ),
        "apiBaseUrl": row.get("api_base_url") or "",
        "softwareVersion": row.get("software_version") or "",
        "lastSeenAt": row.get("last_seen_at"),
        "membershipCount": int(
            row.get("membership_count") or 0
        ),
        "discoveryMembershipCount": int(
            row.get("discovery_membership_count") or 0
        ),
        "managementMembershipCount": int(
            row.get("management_membership_count") or 0
        ),
        "authorityCount": int(
            row.get("authority_count") or 0
        ),
        "metadata": row.get("metadata") or {},
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def instance_list():
    rows = list_nexus_instances()
    instances = [_instance_payload(row) for row in rows]

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "count": len(instances),
        "localCount": sum(
            1 for item in instances if item["isLocal"]
        ),
        "federationEnabledCount": sum(
            1
            for item in instances
            if item["federationEnabled"]
        ),
        "authorityCount": sum(
            item["authorityCount"]
            for item in instances
        ),
        "instances": instances,
    }


def instance_detail(instance_id):
    row = get_nexus_instance(instance_id)

    if not row:
        return None

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "instance": _instance_payload(row),
    }
