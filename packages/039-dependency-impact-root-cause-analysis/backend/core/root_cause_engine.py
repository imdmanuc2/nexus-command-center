def _health(asset):
    for key in ('health_status','health','status','observed_state'):
        value = str(asset.get(key, '')).lower()
        if value:
            return value
    return 'unknown'

def analyze(asset, relationships, assets_by_id):
    asset_id = asset.get('asset_id') or asset.get('id')
    candidates = []
    frontier = [(asset_id, 0, [asset_id])]
    seen = {asset_id}
    while frontier:
        current, distance, path = frontier.pop(0)
        for rel in relationships:
            if rel['source_id'] != current:
                continue
            upstream_id = rel['target_id']
            if upstream_id in seen:
                continue
            seen.add(upstream_id)
            upstream = assets_by_id.get(upstream_id, {'asset_id': upstream_id})
            health = _health(upstream)
            confidence = float(rel.get('confidence') or 70)
            if health in {'critical','offline','failed','unhealthy','down','error'}:
                score = min(99, confidence + max(0, 20 - distance * 5))
                candidates.append({'assetId': upstream_id, 'health': health, 'confidence': round(score, 1), 'path': path + [upstream_id], 'relationshipType': rel['relationship_type']})
            frontier.append((upstream_id, distance + 1, path + [upstream_id]))
    candidates.sort(key=lambda item: item['confidence'], reverse=True)
    if candidates:
        best = candidates[0]
        return {"rootCauseAssetId": best['assetId'], "confidence": best['confidence'], "dependencyPath": best['path'], "evidence": [f"Upstream dependency {best['assetId']} is {best['health']}", f"Relationship: {best['relationshipType']}"]}
    return {"rootCauseAssetId": asset_id, "confidence": 55, "dependencyPath": [asset_id], "evidence": ["No confirmed unhealthy upstream dependency was found", "The selected asset remains the leading candidate"]}
