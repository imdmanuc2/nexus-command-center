import json
from pathlib import Path

SNAPSHOT_DIR = Path("backend/data/snapshots")


def load_snapshot(path):
    return json.loads(path.read_text())


def index_graph(graph):
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = {
        f'{e.get("source")}->{e.get("target")}:{e.get("type")}': e
        for e in graph.get("edges", [])
    }
    return nodes, edges


def latest_two():
    files = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)

    if len(files) < 2:
        return None, None

    return files[1], files[0]


def diff_latest():
    old_path, new_path = latest_two()

    if not old_path or not new_path:
        return {
            "status": "not_enough_snapshots",
            "message": "At least two snapshots are required.",
            "changes": []
        }

    old_graph = load_snapshot(old_path)
    new_graph = load_snapshot(new_path)

    old_nodes, old_edges = index_graph(old_graph)
    new_nodes, new_edges = index_graph(new_graph)

    changes = []

    for node_id, node in new_nodes.items():
        if node_id not in old_nodes:
            changes.append({
                "type": "NODE_ADDED",
                "severity": "info",
                "nodeId": node_id,
                "label": node.get("label"),
                "nodeType": node.get("type")
            })

    for node_id, node in old_nodes.items():
        if node_id not in new_nodes:
            changes.append({
                "type": "NODE_REMOVED",
                "severity": "warning",
                "nodeId": node_id,
                "label": node.get("label"),
                "nodeType": node.get("type")
            })

    for node_id, new_node in new_nodes.items():
        old_node = old_nodes.get(node_id)
        if not old_node:
            continue

        if old_node.get("status") != new_node.get("status"):
            changes.append({
                "type": "NODE_STATUS_CHANGED",
                "severity": "warning",
                "nodeId": node_id,
                "label": new_node.get("label"),
                "from": old_node.get("status"),
                "to": new_node.get("status")
            })

        if old_node.get("label") != new_node.get("label"):
            changes.append({
                "type": "NODE_RENAMED",
                "severity": "info",
                "nodeId": node_id,
                "from": old_node.get("label"),
                "to": new_node.get("label")
            })

    for edge_id, edge in new_edges.items():
        if edge_id not in old_edges:
            changes.append({
                "type": "EDGE_ADDED",
                "severity": "info",
                "source": edge.get("source"),
                "target": edge.get("target"),
                "relationship": edge.get("type")
            })

    for edge_id, edge in old_edges.items():
        if edge_id not in new_edges:
            changes.append({
                "type": "EDGE_REMOVED",
                "severity": "warning",
                "source": edge.get("source"),
                "target": edge.get("target"),
                "relationship": edge.get("type")
            })

    return {
        "status": "ok",
        "fromSnapshot": old_path.name,
        "toSnapshot": new_path.name,
        "changeCount": len(changes),
        "changes": changes
    }
