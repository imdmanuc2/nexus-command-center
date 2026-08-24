from pathlib import Path

path = Path(
    "backend/services/blockchain_operations_service.py"
)

text = path.read_text()

#
# Import
#

import_anchor = (
    "from backend.db.connection import get_connection\n"
)

import_block = (
    "from backend.db.connection import get_connection\n"
    "from backend.services.blockchain_runtime_health_service "
    "import (\n"
    "    derive_blockchain_runtime_health,\n"
    ")\n"
)

if "derive_blockchain_runtime_health" not in text:
    if text.count(import_anchor) != 1:
        raise RuntimeError(
            "Operations import anchor: "
            f"expected 1, found {text.count(import_anchor)}"
        )

    text = text.replace(
        import_anchor,
        import_block,
        1,
    )

#
# Canonical health derivation
#

append_anchor = "        items.append(\n"

health_block = '''        canonical_health = (
            derive_blockchain_runtime_health(
                {
                    "running": (
                        None
                        if running is None
                        else bool(running)
                    ),
                    "nodeStatus": node.get("status"),
                    "lifecycleStatus": node.get(
                        "lifecycle_status"
                    ),
                    "syncStatus": node.get(
                        "sync_status"
                    ),
                    "syncProgress": sync_progress,
                    "blockHeight": node.get(
                        "block_height"
                    ),
                    "headerHeight": node.get(
                        "header_height"
                    ),
                    "initialBlockDownload": (
                        None
                        if ibd is None
                        else bool(ibd)
                    ),
                    "rpcReachable": (
                        None
                        if rpc_reachable is None
                        else bool(rpc_reachable)
                    ),
                    "rpcHealthy": (
                        None
                        if rpc_healthy is None
                        else bool(rpc_healthy)
                    ),
                    "rpcConnected": node.get(
                        "rpc_connected"
                    ),
                }
            )
        )

'''

if "canonical_health = (" not in text:
    if text.count(append_anchor) != 1:
        raise RuntimeError(
            "Operations append anchor: "
            f"expected 1, found {text.count(append_anchor)}"
        )

    text = text.replace(
        append_anchor,
        health_block + append_anchor,
        1,
    )

#
# Output contract
#

output_anchor = '''                "manager": manager_by_runtime.get(asset_id),
                "lastSeenAt": node.get("last_seen_at"),
'''

health_fields = '''                "manager": manager_by_runtime.get(asset_id),

                # Canonical blockchain health dimensions.
                "runtimeState": canonical_health[
                    "runtimeState"
                ],
                "connectivityState": canonical_health[
                    "connectivityState"
                ],
                "syncState": canonical_health[
                    "syncState"
                ],
                "rpcState": canonical_health[
                    "rpcState"
                ],
                "miningReadiness": canonical_health[
                    "miningReadiness"
                ],
                "overallState": canonical_health[
                    "overallState"
                ],
                "stateReason": canonical_health[
                    "stateReason"
                ],

                "lastSeenAt": node.get("last_seen_at"),
'''

if '"runtimeState": canonical_health[' not in text:
    if text.count(output_anchor) != 1:
        raise RuntimeError(
            "Operations output anchor: "
            f"expected 1, found {text.count(output_anchor)}"
        )

    text = text.replace(
        output_anchor,
        health_fields,
        1,
    )

compile(text, str(path), "exec")
path.write_text(text)

print("PASS: Blockchain Operations integration prepared")
