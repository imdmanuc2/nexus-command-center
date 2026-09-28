import inspect

from backend.db.repositories import seymour_registration_repository as repo


def test_unknown_top_level_status_does_not_mask_runtime_state():
    asset = {
        "status": "unknown",
        "telemetry": {
            "runtimeState": "syncing",
            "running": True,
        },
    }

    assert repo._operational_status(asset) == "syncing"


def test_explicit_offline_still_projects_stopped():
    asset = {
        "status": "offline",
        "telemetry": {
            "runtimeState": "syncing",
            "running": True,
        },
    }

    assert repo._operational_status(asset) == "stopped"


def test_projection_prefers_telemetry_sync():
    source = inspect.getsource(repo._upsert_node)

    assert 'telemetry_sync=tel.get("sync")' in source
    assert "sync=telemetry_sync if telemetry_sync else legacy_sync" in source
    assert 'progress=_sync_value(sync,"progressPercent","progress_percent")' in source


def test_projection_preserves_legacy_sync_fallback():
    source = inspect.getsource(repo._upsert_node)

    assert 'legacy_sync=asset.get("sync")' in source
    assert 'height=_sync_value(legacy_sync,"height")' in source
    assert 'headers=_sync_value(legacy_sync,"headers")' in source
    assert (
        'progress=_sync_value(legacy_sync,"progressPercent","progress_percent")'
        in source
    )


def test_explicit_managed_rpc_evidence_is_projected():
    source = inspect.getsource(repo._upsert_node)

    assert 'rpc = tel.get("rpc")' in source
    assert 'rpc_connected = rpc.get("reachable")' in source
    assert 'tel.get("runtimeRpcReachable")' in source
    assert 'operational.get("rpcReachable")' in source
    assert (
        "rpc_connected=COALESCE(%s,nexus.blockchain_nodes.rpc_connected)"
        in source
    )


def test_missing_rpc_evidence_preserves_existing_projection():
    source = inspect.getsource(repo._upsert_node)

    assert "rpc_connected = None" in source
    assert (
        "rpc_connected=COALESCE(%s,nexus.blockchain_nodes.rpc_connected)"
        in source
    )


def test_sync_percent_is_first_class_projection():
    source = inspect.getsource(repo._upsert_node)

    assert "rpc_connected,sync_percent" in source
    assert (
        "sync_percent=COALESCE(EXCLUDED.sync_percent,"
        "nexus.blockchain_nodes.sync_percent)"
        in source
    )


def test_projection_remains_provider_neutral():
    source = inspect.getsource(repo._upsert_node)

    assert 'asset.get("providerId") != "bitcoin-cash-mainnet"' not in source
