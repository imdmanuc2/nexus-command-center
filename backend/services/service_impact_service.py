from backend.services import service_topology_service
from backend.db.repositories import service_impact_repository as repo

_BAD = {'offline', 'failed', 'critical', 'unhealthy', 'error'}
_WARN = {'degraded', 'warning', 'stale', 'unknown'}


def _graph():
    relationships = repo.active_relationships()
    adjacency = {}
    for rel in relationships:
        adjacency.setdefault(rel['source_id'], []).append((rel['target_id'], rel))
        adjacency.setdefault(rel['target_id'], []).append((rel['source_id'], rel))
    return relationships, adjacency


def _walk(seed_ids, adjacency, max_depth=4):
    seen = set(seed_ids)
    frontier = set(seed_ids)
    edges = []
    for _ in range(max_depth):
        nxt = set()
        for node in frontier:
            for neighbor, rel in adjacency.get(node, []):
                edges.append(rel)
                if neighbor not in seen:
                    nxt.add(neighbor)
        if not nxt:
            break
        seen.update(nxt)
        frontier = nxt
    unique = {e['relationship_id']: e for e in edges}
    return seen, list(unique.values())


def analyze(service_id=None):
    topology = service_topology_service.topology()
    relationships, adjacency = _graph()
    results = []
    for service in topology.get('services', []):
        if service_id and service['service_id'] != service_id:
            continue
        members = service.get('members', [])
        seeds = [m['asset_id'] for m in members]
        nodes, edges = _walk(seeds, adjacency)
        asset_rows = repo.assets(nodes)
        by_id = {a['asset_id']: a for a in asset_rows}
        failed = [a for a in asset_rows if str(a.get('operational_state', '')).lower() in _BAD]
        degraded = [a for a in asset_rows if str(a.get('operational_state', '')).lower() in _WARN]
        required_members = {m['asset_id'] for m in members if m.get('required')}
        root_candidates = sorted(failed, key=lambda a: (a['asset_id'] not in required_members, a.get('name') or ''))
        root = root_candidates[0] if root_candidates else (degraded[0] if degraded else None)
        affected = []
        if root:
            affected_nodes, _ = _walk([root['asset_id']], adjacency)
            affected = [by_id[n] for n in affected_nodes if n in by_id and n != root['asset_id']]
        results.append({
            'serviceId': service['service_id'],
            'serviceName': service['name'],
            'health': service.get('health', {}),
            'rootCause': root,
            'affectedAssets': affected,
            'dependencyAssets': asset_rows,
            'dependencyRelationships': edges,
            'criticalPath': [root['asset_id']] + [a['asset_id'] for a in affected] if root else [],
            'analysis': 'root-cause-found' if root else ('not-configured' if not members else 'no-failure-detected'),
        })
    return {'status':'ok','source':'nexus-service-impact-analysis','count':len(results),'services':results}


def dependencies(query=None):
    query = query or {}
    service_id = (query.get('serviceId') or [''])[0] or None
    data = analyze(service_id)
    return {'status':'ok','services':[{
        'serviceId': s['serviceId'], 'serviceName': s['serviceName'],
        'assets': s['dependencyAssets'], 'relationships': s['dependencyRelationships']
    } for s in data['services']]}


def impact(query=None):
    query = query or {}
    service_id = (query.get('serviceId') or [''])[0] or None
    return analyze(service_id)


def root_cause(query=None):
    query = query or {}
    service_id = (query.get('serviceId') or [''])[0] or None
    data = analyze(service_id)
    return {'status':'ok','services':[{
        'serviceId': s['serviceId'], 'serviceName': s['serviceName'],
        'rootCause': s['rootCause'], 'criticalPath': s['criticalPath'],
        'affectedAssetCount': len(s['affectedAssets']), 'analysis': s['analysis']
    } for s in data['services']]}
