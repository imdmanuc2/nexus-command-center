from collections import deque

from backend.core import graph_engine


def load_graph():
    return graph_engine.load()


def node_index(graph):
    return {n["id"]: n for n in graph.get("nodes", [])}


def outgoing_edges(graph, node_id):
    return [e for e in graph.get("edges", []) if e.get("source") == node_id]


def incoming_edges(graph, node_id):
    return [e for e in graph.get("edges", []) if e.get("target") == node_id]


def connected_edges(graph, node_id):
    return [
        e for e in graph.get("edges", [])
        if e.get("source") == node_id or e.get("target") == node_id
    ]


def find_dependents(node_id, max_depth=5):
    """
    Finds everything downstream from this node.
    Example: host -> pool -> worker -> asic
    """
    graph = load_graph()
    nodes = node_index(graph)

    visited = set()
    results = []
    queue = deque([(node_id, 0)])

    while queue:
        current, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for edge in outgoing_edges(graph, current):
            target = edge.get("target")
            if not target or target in visited:
                continue

            visited.add(target)
            target_node = nodes.get(target)

            results.append({
                "depth": depth + 1,
                "relationship": edge.get("type"),
                "node": target_node
            })

            queue.append((target, depth + 1))

    return results


def find_dependencies(node_id, max_depth=5):
    """
    Finds everything upstream this node depends on.
    Example: asic -> worker -> pool -> host
    """
    graph = load_graph()
    nodes = node_index(graph)

    visited = set()
    results = []
    queue = deque([(node_id, 0)])

    while queue:
        current, depth = queue.popleft()

        if depth >= max_depth:
            continue

        for edge in incoming_edges(graph, current):
            source = edge.get("source")
            if not source or source in visited:
                continue

            visited.add(source)
            source_node = nodes.get(source)

            results.append({
                "depth": depth + 1,
                "relationship": edge.get("type"),
                "node": source_node
            })

            queue.append((source, depth + 1))

    return results


def blast_radius(node_id):
    graph = load_graph()
    nodes = node_index(graph)
    root = nodes.get(node_id)

    dependents = find_dependents(node_id, max_depth=8)

    affected = [item["node"] for item in dependents if item.get("node")]

    counts = {}
    for node in affected:
        t = node.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1

    estimated_hashrate = 0
    for node in affected:
        props = node.get("properties", {}) or {}
        estimated_hashrate += float(props.get("hashrate") or 0)

    risk = "low"
    if len(affected) >= 10 or estimated_hashrate > 0:
        risk = "medium"
    if len(affected) >= 25:
        risk = "high"

    return {
        "root": root,
        "affectedCount": len(affected),
        "affectedByType": counts,
        "estimatedHashrateLoss": estimated_hashrate,
        "risk": risk,
        "affected": dependents
    }


def relationship_summary(node_id):
    graph = load_graph()
    nodes = node_index(graph)

    return {
        "node": nodes.get(node_id),
        "dependencies": find_dependencies(node_id),
        "dependents": find_dependents(node_id),
        "blastRadius": blast_radius(node_id),
        "directRelationships": connected_edges(graph, node_id)
    }
