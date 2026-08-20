"""Managed host and storage CMDB enrollment.

Package 077 converts approved managed-host discovery evidence into
canonical CMDB infrastructure objects.

Architectural rules:

* The Nexus CMDB remains the canonical source of truth.
* Discovery evidence is not itself authoritative inventory.
* New hosts require explicit approval before promotion.
* Storage candidates require explicit approval before promotion.
* Environment-specific paths, addresses, and hostnames are never assumed.
* Runtime topology is handled separately by the topology reconciler.
"""

from __future__ import annotations

import hashlib
from typing import Any

from backend.core.asset_manager import (
    get_assets_list,
    upsert_managed_asset,
)
from backend.db.repositories.relationship_repository import (
    upsert_relationship,
)


EXCLUDED_FILESYSTEMS = {
    "tmpfs",
    "devtmpfs",
    "proc",
    "sysfs",
    "cgroup",
    "cgroup2",
    "overlay",
    "squashfs",
    "ramfs",
    "tracefs",
    "debugfs",
    "securityfs",
    "pstore",
    "configfs",
    "fusectl",
    "mqueue",
    "hugetlbfs",
    "autofs",
}

EXCLUDED_MOUNT_PREFIXES = (
    "/boot",
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/snap",
    "/var/lib/docker",
    "/var/lib/containers",
)

NETWORK_FILESYSTEMS = {
    "nfs",
    "nfs4",
    "cifs",
    "smb3",
    "sshfs",
    "fuse.sshfs",
    "ceph",
    "glusterfs",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(
        _text(part).lower()
        for part in parts
        if _text(part)
    )

    if not material:
        raise ValueError(
            f"{prefix} identity requires stable material."
        )

    digest = hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"



def stable_host_identity(
    *,
    machine_id: str = "",
    system_uuid: str = "",
    board_serial: str = "",
    ssh_host_fingerprint: str = "",
    mac_address: str = "",
) -> dict[str, Any]:
    """Resolve a durable host identity from strongest available evidence.

    Identity precedence:

    1. hardware/system serial identity
    2. machine-id
    3. SSH host-key fingerprint
    4. physical MAC address

    Hostname and IP are intentionally excluded because they are mutable
    network/display attributes and may be shared by vendor appliances.
    """

    machine_id = _text(machine_id).lower()
    system_uuid = _text(system_uuid).lower()
    board_serial = _text(board_serial).lower()
    ssh_host_fingerprint = _text(
        ssh_host_fingerprint
    )
    mac_address = _text(mac_address).lower()

    if board_serial:
        identity_type = "board-serial"
        identity_value = board_serial

    elif system_uuid:
        identity_type = "system-uuid"
        identity_value = system_uuid

    elif machine_id:
        identity_type = "machine-id"
        identity_value = machine_id

    elif ssh_host_fingerprint:
        identity_type = "ssh-host-key"
        identity_value = ssh_host_fingerprint

    elif mac_address:
        identity_type = "mac-address"
        identity_value = mac_address

    else:
        raise ValueError(
            "Stable host identity requires board serial, "
            "system UUID, machine-id, SSH fingerprint, or MAC."
        )

    asset_id = _stable_id(
        "asset-host",
        identity_type,
        identity_value,
    )

    return {
        "assetId": asset_id,
        "identityType": identity_type,
        "identityValue": identity_value,
        "machineId": machine_id,
        "systemUuid": system_uuid,
        "boardSerial": board_serial,
        "sshHostFingerprint": ssh_host_fingerprint,
        "macAddress": mac_address,
    }


def build_managed_host_asset_id(
    stable_identity: dict[str, Any],
) -> str:
    asset_id = _text(
        stable_identity.get("assetId")
    )

    if not asset_id:
        raise ValueError(
            "Stable host identity requires assetId."
        )

    return asset_id


def _mount_target(mount: dict[str, Any]) -> str:
    return _text(
        mount.get("target")
        or mount.get("mountpoint")
        or mount.get("mountPoint")
        or mount.get("path")
    )


def _mount_source(mount: dict[str, Any]) -> str:
    return _text(
        mount.get("source")
        or mount.get("device")
    )


def _filesystem(mount: dict[str, Any]) -> str:
    return _text(
        mount.get("fstype")
        or mount.get("fsType")
        or mount.get("filesystem")
    ).lower()


def _is_candidate_mount(
    mount: dict[str, Any],
) -> bool:
    target = _mount_target(mount)
    source = _mount_source(mount)
    filesystem = _filesystem(mount)

    if not target or not source:
        return False

    if filesystem in EXCLUDED_FILESYSTEMS:
        return False

    if any(
        target == prefix
        or target.startswith(prefix + "/")
        for prefix in EXCLUDED_MOUNT_PREFIXES
    ):
        return False

    return True


def _is_network_mount(
    mount: dict[str, Any],
) -> bool:
    filesystem = _filesystem(mount)
    source = _mount_source(mount)

    if filesystem in NETWORK_FILESYSTEMS:
        return True

    # NFS-style server:/export identity.
    if ":" in source and not source.startswith("/"):
        return True

    return False


def _is_bind_subpath_source(
    source: str,
) -> bool:
    """Return True for findmnt backing-source subpath views.

    findmnt may expose bind/root namespace views such as:

        /dev/sda1[/some/subdirectory]

    These are alternate views of an underlying filesystem, not separate
    storage devices and must not become separate CMDB storage assets.
    """

    source = _text(source)

    return (
        "[" in source
        and source.endswith("]")
    )


def _preferred_mount_path(
    paths: list[str],
) -> str:
    clean = sorted({
        _text(path)
        for path in paths
        if _text(path)
    })

    if not clean:
        return ""

    def rank(path: str) -> tuple[int, int, str]:
        # Namespace/root-view aliases are less useful to operators than
        # the directly visible mount path.
        namespace_alias = (
            path.startswith("/mnt/root/")
            or path.startswith("/sd-root/")
            or path.startswith("/mnt/root/sd-root/")
        )

        return (
            1 if namespace_alias else 0,
            path.count("/"),
            path,
        )

    return min(clean, key=rank)


def storage_candidates_from_discovery(
    host_asset: dict[str, Any],
) -> list[dict[str, Any]]:
    """Project discovery evidence into canonical storage candidates.

    Multiple mount views of the same backing storage are collapsed into
    one candidate. Alternate mount paths remain evidence but do not create
    independent CMDB identities.
    """

    host_id = _text(
        host_asset.get("id")
        or host_asset.get("assetId")
    )

    if not host_id:
        raise ValueError(
            "Managed host requires id/assetId."
        )

    observed = _dict(
        host_asset.get("observedState")
    )

    discovery = _dict(
        observed.get("managedHostDiscovery")
    )

    storage = _dict(
        discovery.get("storage")
    )

    mounts = _list(storage.get("mounts"))

    grouped: dict[
        tuple[str, str, str],
        dict[str, Any],
    ] = {}

    for mount in mounts:
        if not isinstance(mount, dict):
            continue

        if not _is_candidate_mount(mount):
            continue

        target = _mount_target(mount)
        source = _mount_source(mount)
        filesystem = _filesystem(mount)
        network = _is_network_mount(mount)

        # Local findmnt bind/subpath views are evidence about an existing
        # filesystem, not independent storage resources.
        if (
            not network
            and _is_bind_subpath_source(source)
        ):
            continue

        if network:
            identity_key = (
                "network",
                source.lower(),
                filesystem,
            )
        else:
            identity_key = (
                host_id.lower(),
                source.lower(),
                filesystem,
            )

        entry = grouped.setdefault(
            identity_key,
            {
                "networkStorage": network,
                "source": source,
                "filesystem": filesystem,
                "mounts": [],
            },
        )

        entry["mounts"].append(dict(mount))

    candidates: list[dict[str, Any]] = []

    for identity_key, entry in grouped.items():
        network = bool(
            entry["networkStorage"]
        )

        source = _text(entry["source"])
        filesystem = _text(
            entry["filesystem"]
        )

        mount_paths = sorted({
            _mount_target(mount)
            for mount in entry["mounts"]
            if _mount_target(mount)
        })

        primary_mount = _preferred_mount_path(
            mount_paths
        )

        if network:
            storage_id = _stable_id(
                "asset-storage",
                "network",
                source,
                filesystem,
            )
        else:
            storage_id = _stable_id(
                "asset-storage",
                host_id,
                source,
                filesystem,
            )

        candidates.append({
            "candidateId": storage_id,
            "assetId": storage_id,
            "assetType": (
                "network-storage"
                if network
                else "storage"
            ),
            "canonicalType": (
                "network-storage"
                if network
                else "storage"
            ),
            "name": (
                source
                if network
                else primary_mount
            ),
            "friendlyName": (
                primary_mount
                or source
            ),
            "displayName": (
                primary_mount
                or source
            ),
            "primaryRole": (
                "Network Storage"
                if network
                else "Host Storage"
            ),
            "purpose": "Blockchain Storage",
            "managed": True,
            "managementModel": "nexus-managed",
            "hostAssetId": host_id,
            "source": source,
            "mountPath": primary_mount,
            "mountPaths": mount_paths,
            "filesystem": filesystem,
            "networkStorage": network,
            "mount": (
                entry["mounts"][0]
                if entry["mounts"]
                else {}
            ),
            "mountEvidence": entry["mounts"],
            "approvalRequired": True,
            "approved": False,
        })

    return sorted(
        candidates,
        key=lambda item: (
            item["networkStorage"],
            item["mountPath"],
            item["source"],
        ),
    )


def build_storage_asset(
    candidate: dict[str, Any],
    *,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    """Build an authoritative CMDB payload from an approved candidate."""

    if not candidate.get("approved"):
        raise ValueError(
            "Storage candidate must be explicitly approved."
        )

    asset_id = _text(
        candidate.get("assetId")
        or candidate.get("candidateId")
    )

    if not asset_id:
        raise ValueError(
            "Storage candidate requires assetId."
        )

    host_asset_id = _text(
        candidate.get("hostAssetId")
    )

    if not host_asset_id:
        raise ValueError(
            "Storage candidate requires hostAssetId."
        )

    mount_path = _text(
        candidate.get("mountPath")
    )
    source = _text(candidate.get("source"))
    filesystem = _text(
        candidate.get("filesystem")
    )

    return {
        "id": asset_id,
        "assetType": _text(
            candidate.get("assetType")
        ) or "storage",
        "canonicalType": _text(
            candidate.get("canonicalType")
        ) or "storage",
        "name": _text(
            candidate.get("name")
        ) or mount_path or source or asset_id,
        "friendlyName": _text(
            candidate.get("friendlyName")
        ) or mount_path or source or asset_id,
        "displayName": _text(
            candidate.get("displayName")
        ) or mount_path or source or asset_id,
        "primaryRole": _text(
            candidate.get("primaryRole")
        ) or "Storage",
        "purpose": _text(
            candidate.get("purpose")
        ) or "Blockchain Storage",
        "managed": True,
        "managementModel": "nexus-managed",
        "capabilities": [
            "blockchain-storage",
            (
                "network-storage"
                if candidate.get("networkStorage")
                else "local-storage"
            ),
        ],
        "observedState": {
            "storage": {
                "hostAssetId": host_asset_id,
                "source": source,
                "mountPath": mount_path,
                "mountPaths": _list(
                    candidate.get("mountPaths")
                ),
                "filesystem": filesystem,
                "networkStorage": bool(
                    candidate.get(
                        "networkStorage"
                    )
                ),
                "mount": _dict(
                    candidate.get("mount")
                ),
            }
        },
        "metadata": {
            "enrollmentSource": (
                "managed-host-discovery"
            ),
            "hostAssetId": host_asset_id,
            "storageSource": source,
            "mountPath": mount_path,
            "mountPaths": _list(
                candidate.get("mountPaths")
            ),
            "filesystem": filesystem,
        },
        "createdAutomatically": False,
        "_actorType": "system",
        "_actorId": actor_id,
        "_source": (
            "managed-host-storage-enrollment"
        ),
        "_reason": (
            "Promote explicitly approved storage "
            "discovery candidate into Nexus CMDB"
        ),
    }


def enroll_storage_candidate(
    candidate: dict[str, Any],
    *,
    actor_id: str = "nexus",
    execute: bool = False,
) -> dict[str, Any]:
    """Plan or execute enrollment of one approved storage candidate."""

    payload = build_storage_asset(
        candidate,
        actor_id=actor_id,
    )

    host_asset_id = _text(
        candidate.get("hostAssetId")
    )

    relationship = {
        "sourceType": "asset",
        "sourceId": host_asset_id,
        "relationshipType": "mounts",
        "targetType": "asset",
        "targetId": payload["id"],
        "status": "active",
        "confidence": 100,
        "source": (
            "managed-host-storage-enrollment"
        ),
        "observed": True,
        "approved": True,
        "metadata": {
            "mountPath": _text(
                candidate.get("mountPath")
            ),
            "source": _text(
                candidate.get("source")
            ),
            "filesystem": _text(
                candidate.get("filesystem")
            ),
        },
    }

    if not execute:
        return {
            "status": "planned",
            "executable": True,
            "asset": payload,
            "relationship": relationship,
        }

    existing_ids = {
        _text(asset.get("id"))
        for asset in get_assets_list()
    }

    if host_asset_id not in existing_ids:
        raise ValueError(
            "Storage enrollment requires an existing "
            "canonical CMDB host asset."
        )

    asset = upsert_managed_asset(payload)
    persisted_relationship = (
        upsert_relationship(relationship)
    )

    return {
        "status": "enrolled",
        "executable": True,
        "asset": asset,
        "relationship": persisted_relationship,
    }


def enrollment_summary(
    host_asset: dict[str, Any],
) -> dict[str, Any]:
    candidates = storage_candidates_from_discovery(
        host_asset
    )

    return {
        "status": "ok",
        "hostAssetId": _text(
            host_asset.get("id")
            or host_asset.get("assetId")
        ),
        "candidateCount": len(candidates),
        "candidates": candidates,
        "executionPerformed": False,
    }


def enroll_managed_host_discovery(
    *,
    identity_stdout: str,
    storage_stdout: str,
    mounts_stdout: str,
    interfaces_stdout: str,
    ports_stdout: str,
    stable_identity: dict[str, Any],
    approved: bool = False,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    """Promote approved host discovery using durable CMDB identity."""

    canonical_asset_id = build_managed_host_asset_id(
        stable_identity
    )

    if not approved:
        return {
            "status": "approval-required",
            "approved": False,
            "assetId": canonical_asset_id,
            "asset": None,
            "executionPerformed": False,
        }

    from backend.services.managed_host_discovery_service import (
        reconcile_managed_host_discovery,
    )

    result = reconcile_managed_host_discovery(
        asset_id=canonical_asset_id,
        identity_stdout=identity_stdout,
        storage_stdout=storage_stdout,
        mounts_stdout=mounts_stdout,
        interfaces_stdout=interfaces_stdout,
        ports_stdout=ports_stdout,
        serial_number=(
            stable_identity.get("boardSerial")
            or stable_identity.get("systemUuid")
            or ""
        ),
        machine_uuid=(
            stable_identity.get("systemUuid")
            or stable_identity.get("machineId")
            or ""
        ),
        ssh_host_key=(
            stable_identity.get("sshHostFingerprint")
            or ""
        ),
        approve_new=True,
        actor_id=actor_id,
    )

    return {
        "status": result.get("status"),
        "approved": True,
        "assetId": canonical_asset_id,
        "stableIdentity": stable_identity,
        "executionPerformed": True,
        "reconciliation": result,
        "asset": result.get("asset"),
    }



def canonicalize_asset_id(
    *,
    old_asset_id: str,
    canonical_asset_id: str,
    execute: bool = False,
) -> dict[str, Any]:
    """Migrate one CMDB asset to a canonical asset ID transactionally.

    This function intentionally uses an explicit allow-list of known
    asset-reference columns rather than guessing from column names.

    When execute=False, only a migration plan is returned.
    """

    old_asset_id = _text(old_asset_id)
    canonical_asset_id = _text(canonical_asset_id)

    if not old_asset_id:
        raise ValueError("old_asset_id is required")

    if not canonical_asset_id:
        raise ValueError("canonical_asset_id is required")

    if old_asset_id == canonical_asset_id:
        raise ValueError(
            "Old and canonical asset IDs must be different."
        )

    from backend.db.connection import get_connection

    # Explicit references to nexus.assets.asset_id or known semantic
    # references that contain canonical asset IDs.
    references = [
        ("alerts", "asset_id"),
        ("asset_components", "asset_id"),
        ("asset_identities", "asset_id"),
        ("asset_lifecycle_history", "asset_id"),
        ("asset_network_addresses", "asset_id"),
        ("asset_operational_profile_history", "asset_id"),
        ("asset_operational_state_history", "asset_id"),
        ("asset_tags", "asset_id"),
        ("audit_events", "asset_id"),
        ("blockchain_nodes", "asset_id"),
        ("business_service_members", "asset_id"),
        ("change_requests", "asset_id"),
        ("compute_capabilities", "asset_id"),
        ("miningcore_instances", "asset_id"),
        ("observations", "matched_asset_id"),
        ("playbook_runs", "asset_id"),
        ("pools", "asset_id"),
        ("reconciliation_cases", "candidate_asset_id"),
        ("service_incidents", "root_cause_asset_id"),
        ("workers", "asset_id"),
        ("workload_assignments", "asset_id"),
        ("workloads", "asset_id"),

        # Semantic non-FK references.
        ("change_execution_attempts", "target_id"),
        ("change_requests", "target_id"),
        ("change_rollback_plans", "target_id"),
        ("dependency_analyses", "root_cause_asset_id"),
        ("operation_queue", "target_id"),
        ("operations_timeline", "source_id"),
        ("playbook_runs", "target_id"),
        ("relationships", "source_id"),
        ("relationships", "target_id"),
        ("service_impact_snapshots", "root_cause_asset_id"),
        ("verification_runs", "target_id"),
        ("workload_assignments", "target_id"),
    ]

    plan: list[dict[str, Any]] = []

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM nexus.assets
                    WHERE asset_id = %s
                ) AS present
                """,
                (old_asset_id,),
            )

            old_exists = bool(
                cursor.fetchone()["present"]
            )

            cursor.execute(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM nexus.assets
                    WHERE asset_id = %s
                ) AS present
                """,
                (canonical_asset_id,),
            )

            canonical_exists = bool(
                cursor.fetchone()["present"]
            )

            if not old_exists:
                raise ValueError(
                    f"Old asset does not exist: {old_asset_id}"
                )

            if canonical_exists:
                raise ValueError(
                    "Canonical asset already exists: "
                    f"{canonical_asset_id}"
                )

            # Only operate on columns that actually exist and whose data
            # type can represent a text asset ID.
            for table, column in references:
                cursor.execute(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'nexus'
                      AND table_name = %s
                      AND column_name = %s
                    """,
                    (table, column),
                )

                row = cursor.fetchone()

                if not row:
                    continue

                data_type = _text(row["data_type"])

                if data_type not in {
                    "text",
                    "character varying",
                    "character",
                }:
                    continue

                from psycopg import sql

                query = sql.SQL(
                    "SELECT COUNT(*) AS count "
                    "FROM nexus.{} "
                    "WHERE {} = %s"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(column),
                )

                cursor.execute(
                    query,
                    (old_asset_id,),
                )

                count = int(
                    cursor.fetchone()["count"]
                )

                if count:
                    plan.append({
                        "table": table,
                        "column": column,
                        "count": count,
                    })

            if not execute:
                connection.rollback()

                return {
                    "status": "planned",
                    "executed": False,
                    "oldAssetId": old_asset_id,
                    "canonicalAssetId": canonical_asset_id,
                    "references": plan,
                }

            from psycopg import sql

            # Dynamically copy every current nexus.assets column while
            # replacing only asset_id. This avoids a fragile hard-coded
            # column list as the CMDB schema evolves.
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'nexus'
                  AND table_name = 'assets'
                ORDER BY ordinal_position
                """
            )

            asset_columns = [
                row["column_name"]
                for row in cursor.fetchall()
            ]

            select_parts = []

            for column in asset_columns:
                if column == "asset_id":
                    select_parts.append(
                        sql.Placeholder()
                    )
                else:
                    select_parts.append(
                        sql.Identifier(column)
                    )

            insert_query = sql.SQL(
                "INSERT INTO nexus.assets ({columns}) "
                "SELECT {values} "
                "FROM nexus.assets "
                "WHERE asset_id = %s"
            ).format(
                columns=sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in asset_columns
                ),
                values=sql.SQL(", ").join(
                    select_parts
                ),
            )

            cursor.execute(
                insert_query,
                (
                    canonical_asset_id,
                    old_asset_id,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Canonical asset copy did not create "
                    "exactly one row."
                )

            migrated: list[dict[str, Any]] = []

            for item in plan:
                update_query = sql.SQL(
                    "UPDATE nexus.{} "
                    "SET {} = %s "
                    "WHERE {} = %s"
                ).format(
                    sql.Identifier(item["table"]),
                    sql.Identifier(item["column"]),
                    sql.Identifier(item["column"]),
                )

                cursor.execute(
                    update_query,
                    (
                        canonical_asset_id,
                        old_asset_id,
                    ),
                )

                migrated.append({
                    **item,
                    "updated": cursor.rowcount,
                })

            # Verify the explicit reference set no longer contains the
            # legacy ID before deleting the old asset.
            remaining: list[dict[str, Any]] = []

            for item in plan:
                check_query = sql.SQL(
                    "SELECT COUNT(*) AS count "
                    "FROM nexus.{} "
                    "WHERE {} = %s"
                ).format(
                    sql.Identifier(item["table"]),
                    sql.Identifier(item["column"]),
                )

                cursor.execute(
                    check_query,
                    (old_asset_id,),
                )

                count = int(
                    cursor.fetchone()["count"]
                )

                if count:
                    remaining.append({
                        "table": item["table"],
                        "column": item["column"],
                        "count": count,
                    })

            if remaining:
                raise RuntimeError(
                    "Legacy asset references remain: "
                    f"{remaining}"
                )

            cursor.execute(
                """
                DELETE FROM nexus.assets
                WHERE asset_id = %s
                """,
                (old_asset_id,),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Legacy asset delete did not remove "
                    "exactly one row."
                )

        connection.commit()

    return {
        "status": "migrated",
        "executed": True,
        "oldAssetId": old_asset_id,
        "canonicalAssetId": canonical_asset_id,
        "references": migrated,
    }
