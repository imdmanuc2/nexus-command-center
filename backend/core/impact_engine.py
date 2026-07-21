def analyze(asset_id, relationships, depth=8):
    adjacency = {}
    reverse = {}
    for rel in relationships:
        source, target = rel['source_id'], rel['target_id']
        adjacency.setdefault(target, []).append((source, rel))
        reverse.setdefault(source, []).append((target, rel))
    impacted, paths, queue = set(), [], [(asset_id, [asset_id])]
    while queue:
        current, path = queue.pop(0)
        if len(path) > depth:
            continue
        for child, rel in adjacency.get(current, []):
            if child in path:
                continue
            impacted.add(child)
            next_path = path + [child]
            paths.append({"assets": next_path, "relationshipType": rel['relationship_type'], "criticality": rel.get('criticality')})
            queue.append((child, next_path))
    upstream, queue = set(), [asset_id]
    while queue:
        current = queue.pop(0)
        for parent, _ in reverse.get(current, []):
            if parent not in upstream:
                upstream.add(parent); queue.append(parent)
    return {"blastRadius": len(impacted), "impactedAssetIds": sorted(impacted), "upstreamAssetIds": sorted(upstream), "paths": paths}
