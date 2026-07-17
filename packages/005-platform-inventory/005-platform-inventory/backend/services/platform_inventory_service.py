"""Unified service for workers, pools, workloads, and relationships."""

from __future__ import annotations

from typing import Any

from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_workers
from backend.db.repositories.workload_repository import list_workloads
from backend.db.repositories.relationship_repository import list_relationships


def inventory() -> dict[str, Any]:
    pools = list_pools()
    workers = list_workers()
    workloads = list_workloads()
    relationships = list_relationships()

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "counts": {
            "pools": len(pools),
            "workers": len(workers),
            "workloads": len(workloads),
            "relationships": len(relationships),
        },
        "pools": pools,
        "workers": workers,
        "workloads": workloads,
        "relationships": relationships,
    }


def topology() -> dict[str, Any]:
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "nodes": {
            "pools": list_pools(),
            "workers": list_workers(),
            "workloads": list_workloads(),
        },
        "relationships": list_relationships(),
    }
