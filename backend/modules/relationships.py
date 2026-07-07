from backend.core.relationship_engine import relationship_summary, blast_radius


def summary(node_id):
    return relationship_summary(node_id)


def impact(node_id):
    return blast_radius(node_id)
