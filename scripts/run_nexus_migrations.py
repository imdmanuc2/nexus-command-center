#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend" / "db" / "migrations"
MANIFEST = ROOT / "backend" / "db" / "migration_manifest.json"

LEGACY_DESCRIPTIONS = {
    "001": "Nexus platform database foundation",
    "002": "Worker pool instances, mining metrics, generic playbook targets, and run steps",
    "003": "Home operations, MiningCore instances, current metrics, rollups, baselines, and enterprise alerts",
    "004": "Durable operations queue, queue events, bulk batches, leasing, retries, cancellation, and progress",
    "005": "Generic telemetry samples, current metrics, rollups, and collector state",
    "006": "Persist blockchain nodes and MiningCore instances",
    "007": "Platform state transition and event engine",
    "008": "Platform alert rules and event-driven alert evaluation",
    "009": "Derived Platform AI context snapshots",
    "010": "Platform recommendation engine",
    "011": "Guarded operations automation engine",
    "012": "Operations timeline and asset history",
    "013": "Natural-key identity reconciliation",
    "014": "Worker identity and activity reconciliation",
    "015": "Live PostgreSQL topology reconciliation",
    "016": "Operations Center Platform layer",
    "017": "Operations Center action execution, approval controls, and audit trail",
    "018": "Managed executor framework and Bitcoin read-only actions",
    "019": "Typed managed host capabilities and secure transport foundation",
    "025": "Asset operational state and immutable state history",
    "026": "CMDB lifecycle and operational state integration",
    "038": "CMDB operational profile and object state framework",
}


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
}


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    migrations = data["migrations"]

    versions = [m["version"] for m in migrations]
    files = [m["file"] for m in migrations]

    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate canonical migration version")

    if len(files) != len(set(files)):
        raise RuntimeError("Duplicate migration file")

    missing = [
        m["file"]
        for m in migrations
        if not (MIGRATIONS / m["file"]).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Missing migration files: " + ", ".join(missing)
        )

    return migrations


def connect():
    required = (
        "NEXUS_DB_HOST",
        "NEXUS_DB_PORT",
        "NEXUS_DB_NAME",
        "NEXUS_DB_USER",
        "NEXUS_DB_PASSWORD",
    )

    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "Missing database environment variables: "
            + ", ".join(missing)
        )

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
            SELECT to_regclass('public.schema_migrations')
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


def fingerprint_state(conn, version):
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
            present.append(cur.fetchone()[0] is not None)

    if all(present):
        return "legacy-applied"

    if any(present):
        return "partial"

    return "pending"


def classify(conn, migrations, applied):
    rows = []

    for migration in migrations:
        version = migration["version"]
        filename = migration["file"]

        if version in applied:
            state = "applied"
        else:
            state = fingerprint_state(conn, version) or "pending"

        rows.append((version, filename, state))

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report migration state without changing the database",
    )
    args = parser.parse_args()

    if not args.status:
        print(
            "ERROR: apply mode is intentionally disabled in this foundation step.",
            file=sys.stderr,
        )
        return 2

    migrations = load_manifest()

    with connect() as conn:
        applied = applied_migrations(conn)
        rows = classify(conn, migrations, applied)

    print("Canonical Nexus migration status")
    print("=" * 88)

    for version, filename, state in rows:
        print(f"{version:>3}  {state:<14}  {filename}")

    print("=" * 88)

    ledger_applied_count = sum(
        state == "applied"
        for _, _, state in rows
    )
    legacy_applied_count = sum(
        state == "legacy-applied"
        for _, _, state in rows
    )
    partial_count = sum(
        state == "partial"
        for _, _, state in rows
    )
    pending_count = sum(
        state == "pending"
        for _, _, state in rows
    )

    print(f"canonical={len(rows)}")
    print(f"ledgerApplied={ledger_applied_count}")
    print(f"legacyApplied={legacy_applied_count}")
    print(f"partial={partial_count}")
    print(f"pending={pending_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
