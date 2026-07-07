from backend.core.assets import get_assets_list
from backend.modules import discovery
from backend.modules import mining


def pool_node_id(pool):
    return f"pool-{pool.get('id', 'unknown')}-{pool.get('host', 'unknown').replace('.', '-')}"


def host_node_id(host):
    return f"host-{str(host).replace('.', '-')}"


def worker_node_id(worker):
    return f"worker-{worker.get('workerName') or worker.get('name') or worker.get('workerId')}"


def add_node(nodes, node):
    nodes[node["id"]] = node


def add_edge(edges, source, target, rel_type, label=None):
    if not source or not target:
        return

    edge = {
        "source": source,
        "target": target,
        "type": rel_type,
        "label": label or rel_type.replace("_", " ").title()
    }

    if edge not in edges:
        edges.append(edge)


def build_graph():
    topo_payload = discovery.topology()
    topo = topo_payload.get("topology", {})
    discovery_data = topo_payload.get("discovery", {})

    assets = get_assets_list()

    try:
        mining_data = mining.workers()
        workers = mining_data.get("workers", [])
    except Exception:
        workers = []

    pools = topo.get("pools", [])
    systems = discovery_data.get("systems", [])

    nodes = {}
    edges = []

    # Hosts
    for system in systems:
        ip = system.get("ip")
        asset = system.get("asset", {})

        add_node(nodes, {
            "id": host_node_id(ip),
            "type": "host",
            "label": asset.get("friendlyName") or asset.get("name") or ip,
            "status": system.get("health", {}).get("level", "unknown"),
            "properties": {
                "ip": ip,
                "primaryRole": system.get("primaryRole"),
                "openPorts": system.get("openPorts", []),
                "health": system.get("health", {}),
                "profile": system.get("profile", {})
            }
        })

    # Pools
    for pool in pools:
        pid = pool_node_id(pool)
        host_id = host_node_id(pool.get("host"))

        add_node(nodes, {
            "id": pid,
            "type": "pool",
            "label": pool.get("name") or pool.get("id"),
            "status": "online",
            "properties": pool
        })

        add_edge(edges, pid, host_id, "HOSTED_ON")

    # Assets
    for asset in assets:
        aid = asset.get("id")

        add_node(nodes, {
            "id": aid,
            "type": asset.get("type", "asset"),
            "label": asset.get("friendlyName") or asset.get("name") or asset.get("ip"),
            "status": "online",
            "properties": asset
        })

        if asset.get("ip"):
            add_edge(edges, aid, host_node_id(asset.get("ip")), "HAS_NETWORK_IDENTITY")

        if asset.get("poolId") and asset.get("poolHost"):
            matching_pool = next(
                (
                    p for p in pools
                    if p.get("id") == asset.get("poolId")
                    and p.get("host") == asset.get("poolHost")
                ),
                None
            )

            if matching_pool:
                add_edge(edges, aid, pool_node_id(matching_pool), "MINES_ON")

    # Workers
    for worker in workers:
        wid = worker_node_id(worker)

        add_node(nodes, {
            "id": wid,
            "type": "worker",
            "label": worker.get("displayName") or worker.get("workerName") or worker.get("name"),
            "status": "online",
            "properties": worker
        })

        asset = next(
            (
                a for a in assets
                if str(a.get("workerId", "")).zfill(3) == str(worker.get("workerName") or worker.get("name") or "").zfill(3)
            ),
            None
        )

        if asset:
            add_edge(edges, asset.get("id"), wid, "RUNS_WORKER")

        matching_pool = next(
            (
                p for p in pools
                if p.get("id") == worker.get("poolId")
                and p.get("host") == (worker.get("poolHost") or worker.get("host"))
            ),
            None
        )

        if matching_pool:
            add_edge(edges, wid, pool_node_id(matching_pool), "MINES_ON")

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "assets": len(assets),
            "pools": len(pools),
            "workers": len(workers),
            "hosts": len(systems)
        }
    }


def relationships_for(node_id):
    graph = build_graph()
    edges = [
        edge for edge in graph["edges"]
        if edge["source"] == node_id or edge["target"] == node_id
    ]

    return {
        "nodeId": node_id,
        "relationships": edges,
        "graph": graph
    }
