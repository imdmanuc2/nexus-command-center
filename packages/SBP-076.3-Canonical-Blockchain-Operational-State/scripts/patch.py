from pathlib import Path

path = Path("backend/services/blockchain_operations_service.py")
text = path.read_text()

old = '''        state = str(
            node.get("sync_status")
            or node.get("status")
            or "unknown"
        ).lower()

        # Canonical live-runtime precedence.
        if running == 0:
            state = "stopped"
        elif ibd == 1 and rpc_reachable == 1:
            state = "syncing"
        elif running == 1 and rpc_healthy == 1:
            state = "running"
'''

new = '''        sync_status = str(
            node.get("sync_status") or ""
        ).strip().lower()

        node_status = str(
            node.get("status") or ""
        ).strip().lower()

        # Canonical provider-neutral operational-state precedence.
        #
        # New Seymour-managed runtimes expose lifecycle state through
        # current_metrics. Older/native blockchain discovery may instead
        # expose node status and rpc_connected directly on blockchain_nodes.
        #
        # Do not allow placeholder values such as "unknown" to mask useful
        # lower-level evidence.
        if running == 0:
            state = "stopped"
        elif ibd == 1 and rpc_reachable == 1:
            state = "syncing"
        elif running == 1 and rpc_healthy == 1:
            state = "running"
        elif running == 1:
            state = "running"
        elif sync_status and sync_status != "unknown":
            state = sync_status
        elif node_status and node_status != "unknown":
            state = node_status
        elif node.get("rpc_connected") is True:
            state = "online"
        else:
            state = "unknown"
'''

if old not in text:
    raise SystemExit(
        "Expected blockchain operational-state block was not found."
    )

text = text.replace(old, new, 1)

# Expose the legacy/native RPC-connected field to the projection.
old_select = '''                    n.peer_count,
                    n.observed_state,
                    n.updated_at,
'''

new_select = '''                    n.peer_count,
                    n.rpc_connected,
                    n.observed_state,
                    n.updated_at,
'''

if old_select not in text:
    raise SystemExit(
        "Expected blockchain node SELECT block was not found."
    )

text = text.replace(old_select, new_select, 1)

path.write_text(text)

print(f"Patched {path}")
