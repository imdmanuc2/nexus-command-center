#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend" / "db" / "migrations"
MANIFEST = ROOT / "backend" / "db" / "migration_manifest.json"


FINGERPRINTS = {
    "004": (
        "nexus.operation_queue",
        "nexus.operation_queue_events",
        "nexus.operation_batches",
    ),
    "020": (
        "nexus.operation_sessions",
        "nexus.operation_session_events",
    ),
    "021": (
        "nexus.playbooks",
        "nexus.playbook_versions",
        "nexus.playbook_runs",
        "nexus.playbook_steps",
    ),
    "022": (
        "nexus.execution_policies",
        "nexus.policy_decisions",
    ),
    "023": (
        "nexus.maintenance_windows",
        "nexus.maintenance_targets",
    ),
    "024": (
        "nexus.software_packages",
        "nexus.deployment_jobs",
        "nexus.deployment_targets",
    ),
    "027": (
        "nexus.relationship_type_catalog",
        "nexus.relationship_history",
        "nexus.compute_capabilities",
        "nexus.workload_assignments",
    ),
    "028": (
        "nexus.engineering_knowledge",
        "nexus.dependency_analyses",
        "nexus.incident_resolution_outcomes",
    ),
    "029": (
        "nexus.business_services",
        "nexus.business_service_members",
        "nexus.business_service_dependencies",
        "nexus.business_service_history",
    ),
    "030": (
        "nexus.service_health_snapshots",
        "nexus.service_incidents",
        "nexus.service_availability_rollups",
    ),
    "031": (
        "nexus.business_service_membership_rules",
        "nexus.business_service_reconciliation_runs",
    ),
    "032": (
        "nexus.service_impact_snapshots",
        "nexus.service_dependency_rules",
    ),
    "033": (
        "nexus.maintenance_history",
    ),
    "034": (
        "nexus.change_templates",
        "nexus.change_requests",
        "nexus.change_steps",
        "nexus.change_approvals",
        "nexus.change_execution_log",
    ),
    "035": (
        "nexus.change_execution_workers",
        "nexus.change_execution_attempts",
    ),
    "036": (
        "nexus.change_rollback_plans",
        "nexus.change_rollback_attempts",
        "nexus.change_rollback_events",
    ),
    "037": (
        "nexus.verification_profiles",
        "nexus.verification_profile_steps",
        "nexus.verification_runs",
        "nexus.verification_step_runs",
        "nexus.verification_evidence",
        "nexus.verification_events",
    ),
    "039": (
        "nexus.seymour_registrations",
    ),
    "040": (
        "nexus.organizations",
        "nexus.nexus_instances",
    ),
    "041": (
        "nexus.asset_instance_memberships",
    ),
}


def load_manifest():
    data = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    migrations = data["migrations"]

    versions = [
        migration["version"]
        for migration in migrations
    ]

    files = [
        migration["file"]
        for migration in migrations
    ]

    if len(versions) != len(set(versions)):
        raise RuntimeError(
            "Duplicate canonical migration version"
        )

    if len(files) != len(set(files)):
        raise RuntimeError(
            "Duplicate migration file"
        )

    missing = [
        migration["file"]
        for migration in migrations
        if not (
            MIGRATIONS / migration["file"]
        ).is_file()
    ]

    if missing:
        raise RuntimeError(
            "Missing migration files: "
            + ", ".join(missing)
        )

    return migrations


def required_database_environment():
    required = (
        "NEXUS_DB_HOST",
        "NEXUS_DB_PORT",
        "NEXUS_DB_NAME",
        "NEXUS_DB_USER",
        "NEXUS_DB_PASSWORD",
    )

    missing = [
        name
        for name in required
        if not os.getenv(name)
    ]

    if missing:
        raise RuntimeError(
            "Missing database environment variables: "
            + ", ".join(missing)
        )


def connect():
    required_database_environment()

    return psycopg.connect(
        host=os.environ["NEXUS_DB_HOST"],
        port=int(os.environ["NEXUS_DB_PORT"]),
        dbname=os.environ["NEXUS_DB_NAME"],
        user=os.environ["NEXUS_DB_USER"],
        password=os.environ["NEXUS_DB_PASSWORD"],
    )


def applied_migrations(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT to_regclass(
                'public.schema_migrations'
            )
            """
        )

        exists = cur.fetchone()[0]

        if not exists:
            return {}

        cur.execute(
            """
            SELECT version, description
            FROM public.schema_migrations
            ORDER BY version
            """
        )

        return dict(cur.fetchall())


def fingerprint_state(
    conn,
    version,
):
    objects = FINGERPRINTS.get(version)

    if not objects:
        return None

    present = []

    with conn.cursor() as cur:
        for object_name in objects:
            cur.execute(
                "SELECT to_regclass(%s)",
                (object_name,),
            )

            present.append(
                cur.fetchone()[0] is not None
            )

    if all(present):
        return "legacy-applied"

    if any(present):
        return "partial"

    return "pending"


def classify(
    conn,
    migrations,
    applied,
):
    rows = []

    for migration in migrations:
        version = migration["version"]
        filename = migration["file"]

        if version in applied:
            state = "applied"
        else:
            state = (
                fingerprint_state(
                    conn,
                    version,
                )
                or "pending"
            )

        rows.append(
            (
                version,
                filename,
                state,
            )
        )

    return rows


def current_status(migrations):
    with connect() as conn:
        applied = applied_migrations(conn)

        return classify(
            conn,
            migrations,
            applied,
        )


def report(rows):
    print(
        "Canonical Nexus migration status"
    )

    print("=" * 88)

    for version, filename, state in rows:
        print(
            f"{version:>3}  "
            f"{state:<14}  "
            f"{filename}"
        )

    print("=" * 88)

    summary = {
        "canonical": len(rows),
        "ledgerApplied": sum(
            state == "applied"
            for _, _, state in rows
        ),
        "legacyApplied": sum(
            state == "legacy-applied"
            for _, _, state in rows
        ),
        "partial": sum(
            state == "partial"
            for _, _, state in rows
        ),
        "pending": sum(
            state == "pending"
            for _, _, state in rows
        ),
    }

    for key in (
        "canonical",
        "ledgerApplied",
        "legacyApplied",
        "partial",
        "pending",
    ):
        print(
            f"{key}={summary[key]}"
        )

    return summary


def psql_environment():
    required_database_environment()

    environment = os.environ.copy()

    environment["PGPASSWORD"] = (
        os.environ["NEXUS_DB_PASSWORD"]
    )

    return environment


def apply_migration(migration):
    version = migration["version"]
    filename = migration["file"]
    migration_path = MIGRATIONS / filename

    print(
        f"Applying {version} :: {filename}",
        flush=True,
    )

    subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            os.environ["NEXUS_DB_HOST"],
            "-p",
            os.environ["NEXUS_DB_PORT"],
            "-U",
            os.environ["NEXUS_DB_USER"],
            "-d",
            os.environ["NEXUS_DB_NAME"],
            "-f",
            str(migration_path),
        ],
        env=psql_environment(),
        check=True,
    )


def apply_pending(
    migrations,
    rows,
):
    summary = report(rows)

    if summary["partial"]:
        print(
            "ERROR: refusing migration apply "
            "because partial historical "
            "migrations were detected.",
            file=sys.stderr,
        )

        return 3

    if summary["legacyApplied"]:
        print(
            "ERROR: refusing migration apply "
            "because legacy-applied migrations "
            "require explicit reconciliation.",
            file=sys.stderr,
        )

        return 4

    pending = {
        version
        for version, _, state in rows
        if state == "pending"
    }

    if not pending:
        print(
            "No canonical migrations pending."
        )

        return 0

    for migration in migrations:
        if migration["version"] in pending:
            apply_migration(migration)

    final_rows = current_status(migrations)

    final_summary = report(
        final_rows
    )

    expected = {
        "canonical": len(migrations),
        "ledgerApplied": len(migrations),
        "legacyApplied": 0,
        "partial": 0,
        "pending": 0,
    }

    if final_summary != expected:
        print(
            "ERROR: canonical migration "
            "verification failed.",
            file=sys.stderr,
        )

        return 5

    print(
        "PASS: all canonical migrations applied."
    )

    return 0


def main():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--status",
        action="store_true",
        help=(
            "Report migration state "
            "without changing the database"
        ),
    )

    mode.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply pending canonical "
            "migrations"
        ),
    )

    args = parser.parse_args()

    migrations = load_manifest()
    rows = current_status(migrations)

    if args.status:
        report(rows)
        return 0

    return apply_pending(
        migrations,
        rows,
    )


if __name__ == "__main__":
    raise SystemExit(main())
