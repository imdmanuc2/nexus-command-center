from backend.core.graph import build_graph, relationships_for


def graph():
    return build_graph()


def relationships(node_id):
    return relationships_for(node_id)
