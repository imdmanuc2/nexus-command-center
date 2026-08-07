from backend.db.repositories import service_topology_repository as repo

_BAD = {'offline', 'failed', 'critical', 'unhealthy', 'error'}
_DEGRADED = {'degraded', 'warning', 'stale', 'unknown'}
_SUPPRESSED = {'maintenance', 'disabled', 'retired', 'decommissioning'}


def _health(service, members):
    active = [m for m in members if str(m.get('asset_operational_state', 'active')).lower() not in _SUPPRESSED]
    required = [m for m in active if m.get('required')]
    failed = [m for m in required if str(m.get('asset_status', '')).lower() in _BAD]
    degraded = [m for m in active if str(m.get('asset_status', '')).lower() in _DEGRADED]
    if str(service.get('operational_state', 'active')).lower() in _SUPPRESSED:
        state = 'suppressed'
    elif failed:
        state = 'critical'
    elif degraded:
        state = 'degraded'
    elif not members:
        state = 'not-configured'
    elif not active:
        state = 'unknown'
    else:
        state = 'healthy'
    available = max(0, len(active) - len(failed) - len(degraded))
    capacity = round((available / len(active)) * 100, 1) if active else 0
    return {'state': state, 'capacityPercent': capacity, 'memberCount': len(members),
            'activeMemberCount': len(active), 'failedRequiredCount': len(failed),
            'degradedCount': len(degraded), 'failedAssets': [m['asset_id'] for m in failed]}


def topology(_query=None):
    services = repo.services()
    all_members = repo.members()
    all_dependencies = repo.dependencies()
    payload = []
    for service in services:
        sid = service['service_id']
        members = [m for m in all_members if m['service_id'] == sid]
        item = dict(service)
        item['health'] = _health(service, members)
        item['members'] = members
        item['workloads'] = repo.workload_counts(sid)
        item['dependencies'] = [d for d in all_dependencies if d['service_id'] == sid]
        payload.append(item)
    summary = {k: sum(1 for s in payload if s['health']['state'] == k) for k in ('healthy','degraded','critical','suppressed','unknown','not-configured')}
    return {'status':'ok','source':'nexus-cmdb-business-services','summary':summary,
            'serviceCount':len(payload),'services':payload,'serviceDependencies':all_dependencies}


def detail(query):
    service_id = (query.get('serviceId') or [''])[0]
    if not service_id:
        raise ValueError('serviceId is required')
    service = repo.service(service_id)
    if not service:
        raise KeyError(service_id)
    members = repo.members(service_id)
    return {'status':'ok','service':service,'health':_health(service,members),'members':members,
            'workloads':repo.workload_counts(service_id),'dependencies':repo.dependencies(service_id)}
