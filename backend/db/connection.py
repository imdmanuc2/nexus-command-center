"""Shared PostgreSQL connection utilities for Nexus."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = (
    PROJECT_ROOT
    / "backend"
    / "data"
    / "private"
    / "cmdb.env"
)


def _load_env_file(path: Path = DEFAULT_ENV_FILE) -> None:
    """Load KEY=value settings without replacing existing environment."""

    if not path.exists():
        raise RuntimeError(
            f"Nexus database environment file not found: {path}"
        )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def database_settings() -> dict[str, object]:
    _load_env_file()

    required = (
        "NEXUS_DB_HOST",
        "NEXUS_DB_PORT",
        "NEXUS_DB_NAME",
        "NEXUS_DB_USER",
        "NEXUS_DB_PASSWORD",
    )

    missing = [
        key
        for key in required
        if not os.environ.get(key)
    ]

    if missing:
        raise RuntimeError(
            "Missing Nexus PostgreSQL settings: "
            + ", ".join(missing)
        )

    return {
        "host": os.environ["NEXUS_DB_HOST"],
        "port": int(os.environ["NEXUS_DB_PORT"]),
        "dbname": os.environ["NEXUS_DB_NAME"],
        "user": os.environ["NEXUS_DB_USER"],
        "password": os.environ["NEXUS_DB_PASSWORD"],
        "connect_timeout": 5,
        "row_factory": dict_row,
    }


def get_connection() -> psycopg.Connection:
    """Return a new PostgreSQL connection."""

    return psycopg.connect(**database_settings())


@contextmanager
def transaction() -> Iterator[psycopg.Connection]:
    """Provide a transaction that commits or rolls back automatically."""

    connection = get_connection()

    try:
        with connection.transaction():
            yield connection
    finally:
        connection.close()


def healthcheck() -> dict[str, object]:
    """Verify Nexus can connect and read its PostgreSQL schema."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    NOW() AS checked_at,
                    (
                        SELECT COUNT(*)
                        FROM pg_tables
                        WHERE schemaname = 'nexus'
                    ) AS nexus_table_count
                """
            )

            row = cursor.fetchone()

    return {
        "status": "ok",
        **dict(row or {}),
    }
