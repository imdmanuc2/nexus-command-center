from backend.core.asset_classifier import classify_graph_payload
from backend.core.graph import build_graph


def graph():
    payload = build_graph()
    return classify_graph_payload(payload)
