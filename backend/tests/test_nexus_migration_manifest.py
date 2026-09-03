import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "backend" / "db" / "migrations"
MANIFEST = ROOT / "backend" / "db" / "migration_manifest.json"
RUNNER = ROOT / "scripts" / "run_nexus_migrations.py"


def canonical_disk_files():
    return sorted(
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if (
            len(path.name) >= 4
            and path.name[:3].isdigit()
            and path.name[3] == "_"
        )
    )


def manifest_rows():
    return json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )["migrations"]


def load_runner_module():
    spec = importlib.util.spec_from_file_location(
        "nexus_migration_runner_test",
        RUNNER,
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_manifest_exactly_matches_numbered_sql_inventory():
    rows = manifest_rows()

    manifest_files = [
        row["file"]
        for row in rows
    ]

    assert manifest_files == canonical_disk_files()

    versions = [
        row["version"]
        for row in rows
    ]

    assert len(versions) == len(set(versions))
    assert len(manifest_files) == len(set(manifest_files))

    assert versions == [
        f"{number:03d}"
        for number in range(
            1,
            len(versions) + 1,
        )
    ]


def test_manifest_includes_pairing_tail():
    rows = manifest_rows()

    assert rows[-2:] == [
        {
            "version": "047",
            "file": "047_nexus_peer_outbound_pairing.sql",
        },
        {
            "version": "048",
            "file": "048_nexus_peer_enrollment_idempotency.sql",
        },
    ]


def test_runner_rejects_unmanifested_numbered_migration(
    tmp_path,
    monkeypatch,
):
    runner = load_runner_module()

    migrations = tmp_path / "migrations"
    migrations.mkdir()

    (migrations / "001_test.sql").write_text(
        "SELECT 1;\n",
        encoding="utf-8",
    )

    (migrations / "002_unmanifested.sql").write_text(
        "SELECT 2;\n",
        encoding="utf-8",
    )

    manifest = tmp_path / "migration_manifest.json"

    manifest.write_text(
        json.dumps(
            {
                "manifestVersion": 1,
                "migrations": [
                    {
                        "version": "001",
                        "file": "001_test.sql",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        runner,
        "MIGRATIONS",
        migrations,
    )

    monkeypatch.setattr(
        runner,
        "MANIFEST",
        manifest,
    )

    with pytest.raises(
        RuntimeError,
        match="Unmanifested canonical migration files",
    ):
        runner.load_manifest()
