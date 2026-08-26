"""Repository for Nexus organization, site, and instance identity."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def register_local_instance(identity: dict[str, Any]) -> dict[str, Any]:
    organization_id = _text(identity.get("organizationId"))
    organization_name = _text(identity.get("organizationName")) or organization_id

    site_id = _text(identity.get("siteId"))
    site_name = _text(identity.get("siteName")) or site_id

    instance_id = _text(identity.get("instanceId"))
    instance_name = _text(identity.get("instanceName")) or instance_id
    hostname = _text(identity.get("hostname"))

    if not organization_id:
        raise ValueError("organizationId is required")

    if not site_id:
        raise ValueError("siteId is required")

    if not instance_id:
        raise ValueError("instanceId is required")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    instance_id,
                    organization_id,
                    site_id,
                    is_local
                FROM nexus.nexus_instances
                WHERE instance_id = %s
                """,
                (instance_id,),
            )

            existing_instance = cursor.fetchone()

            if existing_instance:
                existing_org = _text(existing_instance["organization_id"])
                existing_site = _text(existing_instance["site_id"])

                if existing_org and existing_org != organization_id:
                    raise RuntimeError(
                        "Nexus instance organization conflict: "
                        f"{instance_id} belongs to {existing_org}, "
                        f"not {organization_id}"
                    )

                if existing_site and existing_site != site_id:
                    raise RuntimeError(
                        "Nexus instance site conflict: "
                        f"{instance_id} belongs to {existing_site}, "
                        f"not {site_id}"
                    )

            cursor.execute(
                """
                INSERT INTO nexus.organizations (
                    organization_id,
                    name,
                    status,
                    metadata,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    'active',
                    %s,
                    NOW()
                )
                ON CONFLICT (organization_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    status = 'active',
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    organization_id,
                    organization_name,
                    Jsonb({
                        "source": "nexus-runtime-registration",
                    }),
                ),
            )

            organization = dict(cursor.fetchone())

            cursor.execute(
                """
                SELECT organization_id
                FROM nexus.sites
                WHERE site_id = %s
                """,
                (site_id,),
            )

            existing_site_row = cursor.fetchone()

            if existing_site_row:
                existing_site_org = _text(
                    existing_site_row["organization_id"]
                )

                if (
                    existing_site_org
                    and existing_site_org != organization_id
                ):
                    raise RuntimeError(
                        "Nexus site organization conflict: "
                        f"{site_id} belongs to {existing_site_org}, "
                        f"not {organization_id}"
                    )

            cursor.execute(
                """
                INSERT INTO nexus.sites (
                    site_id,
                    name,
                    organization_id,
                    status,
                    metadata,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'active',
                    %s,
                    NOW()
                )
                ON CONFLICT (site_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    organization_id = COALESCE(
                        nexus.sites.organization_id,
                        EXCLUDED.organization_id
                    ),
                    status = 'active',
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    site_id,
                    site_name,
                    organization_id,
                    Jsonb({
                        "source": "nexus-runtime-registration",
                    }),
                ),
            )

            site = dict(cursor.fetchone())

            cursor.execute(
                """
                INSERT INTO nexus.nexus_instances (
                    instance_id,
                    organization_id,
                    site_id,
                    name,
                    hostname,
                    instance_role,
                    status,
                    is_local,
                    federation_enabled,
                    software_version,
                    last_seen_at,
                    metadata,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'site-controller',
                    'active',
                    TRUE,
                    FALSE,
                    %s,
                    NOW(),
                    %s,
                    NOW()
                )
                ON CONFLICT (instance_id)
                DO UPDATE SET
                    organization_id = COALESCE(
                        nexus.nexus_instances.organization_id,
                        EXCLUDED.organization_id
                    ),
                    site_id = COALESCE(
                        nexus.nexus_instances.site_id,
                        EXCLUDED.site_id
                    ),
                    name = EXCLUDED.name,
                    hostname = EXCLUDED.hostname,
                    status = 'active',
                    is_local = TRUE,
                    last_seen_at = NOW(),
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    instance_id,
                    organization_id,
                    site_id,
                    instance_name,
                    hostname,
                    _text(identity.get("softwareVersion")),
                    Jsonb({
                        "identitySource": _text(
                            identity.get("identitySource")
                        ),
                    }),
                ),
            )

            instance = dict(cursor.fetchone())

        connection.commit()

    return {
        "organization": organization,
        "site": site,
        "instance": instance,
    }


def get_local_instance() -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM nexus.nexus_instances
                WHERE is_local = TRUE
                LIMIT 1
                """
            )

            row = cursor.fetchone()

    return dict(row) if row else None
