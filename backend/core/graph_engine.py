import json
from datetime import datetime, timezone
from pathlib import Path

from backend.core.graph import build_graph

GRAPH_DIR = Path("backend/data/graph")
SNAPSHOT_DIR = Path("backend/data/snapshots")
LIVE_GRAPH = GRAPH_DIR / "live.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def rebuild(save_snapshot=True):
    ensure_dirs()

    graph = build_graph()
    graph["generatedAt"] = now_iso()
    graph["graphVersion"] = "nexus-graph-v1"

    LIVE_GRAPH.write_text(json.dumps(graph, indent=2) + "\n")

    if save_snapshot:
        snapshot_name = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S") + ".json"
        snapshot_path = SNAPSHOT_DIR / snapshot_name
        snapshot_path.write_text(json.dumps(graph, indent=2) + "\n")

    return graph


def load():
    ensure_dirs()

    if not LIVE_GRAPH.exists():
        return rebuild(save_snapshot=True)

    return json.loads(LIVE_GRAPH.read_text())


def snapshots(limit=20):
    ensure_dirs()

    files = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)[:limit]

    return {
        "snapshots": [
            {
                "file": f.name,
                "createdAt": f.stem,
                "size": f.stat().st_size
            }
            for f in files
        ]
    }


def node(node_id):
    graph = load()
    found = next((n for n in graph.get("nodes", []) if n.get("id") == node_id), None)

    return {
        "node": found,
        "relationships": [
            e for e in graph.get("edges", [])
            if e.get("source") == node_id or e.get("target") == node_id
        ]
    }


def statistics():
    graph = load()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    by_type = {}
    for n in nodes:
        t = n.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "generatedAt": graph.get("generatedAt"),
        "graphVersion": graph.get("graphVersion"),
        "counts": graph.get("counts", {}),
        "nodeTypes": by_type,
        "nodes": len(nodes),
        "edges": len(edges)
    }
