from datetime import datetime, timezone
from backend.services import service_topology_service
from backend.db.repositories import service_operations_repository as repo

_BAD = {'critical', 'offline'}
_WARN = {'degraded', 'warning', 'unknown'}
_NON_MONITORED = {'not-configured', 'suppressed'}


def _topology():
    return service_topology_service.topology()


def _service_incident(service):
    health = service.get('health', {})
    state = health.get('state', 'unknown')
    if state in _NON_MONITORED or state not in _BAD | _WARN:
        return None
    failed = health.get('failedAssets', [])
    severity = 'critical' if state in _BAD else 'degraded'
    return {
        'incidentId': f"live-{service['service_id']}",
        'serviceId': service['service_id'],
        'serviceName': service['name'],
        'severity': severity,
        'status': 'open',
        'title': f"{service['name']} is {state}",
        'summary': f"{health.get('failedRequiredCount', 0)} required component(s) failed and {health.get('degradedCount', 0)} component(s) are degraded.",
        'affectedAssets': failed,
        'source': 'live-service-health',
    }


def health():
    data = _topology()
    return {
        'status': 'healthy',
        'component': 'nexus-api',
        'database': 'healthy',
        'serviceTopology': 'healthy',
        'serviceCount': data.get('serviceCount', 0),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def dashboard(_query=None):
    data = _topology()
    services = data.get('services', [])
    live_incidents = [i for i in (_service_incident(s) for s in services) if i]
    try:
        persisted = repo.open_incidents()
    except Exception:
        persisted = []
    configured_services = [s for s in services if s.get('health', {}).get('state') != 'not-configured']
    capacity_values = [float(s.get('health', {}).get('capacityPercent', 0)) for s in configured_services]
    avg_capacity = round(sum(capacity_values) / len(capacity_values), 1) if capacity_values else 0
    critical_services = [s for s in services if s.get('criticality') == 'critical']
    unavailable = [s for s in critical_services if s.get('health', {}).get('state') in _BAD]
    return {
        'status': 'ok',
        'source': 'nexus-service-operations',
        'summary': {
            **data.get('summary', {}),
            'serviceCount': len(services),
            'openIncidentCount': len(live_incidents) + len(persisted),
            'averageCapacityPercent': avg_capacity,
            'criticalServiceAvailabilityPercent': round(((len(critical_services)-len(unavailable))/len(critical_services))*100, 1) if critical_services else 100,
        },
        'services': services,
        'incidents': live_incidents + persisted,
        'serviceDependencies': data.get('serviceDependencies', []),
        'generatedAt': datetime.now(timezone.utc).isoformat(),
    }


def service_health(_query=None):
    data = _topology()
    return {'status': 'ok', 'summary': data.get('summary', {}), 'services': [
        {'serviceId': s['service_id'], 'name': s['name'], 'criticality': s['criticality'], 'health': s['health']}
        for s in data.get('services', [])
    ]}


def incidents(_query=None):
    data = _topology()
    live = [i for i in (_service_incident(s) for s in data.get('services', [])) if i]
    try:
        persisted = repo.open_incidents()
    except Exception:
        persisted = []
    return {'status': 'ok', 'count': len(live)+len(persisted), 'incidents': live+persisted}


def capacity(_query=None):
    data = _topology()
    rows = []
    for s in data.get('services', []):
        h = s.get('health', {})
        active = int(h.get('activeMemberCount', 0))
        failed = int(h.get('failedRequiredCount', 0)) + int(h.get('degradedCount', 0))
        available = max(0, active-failed)
        redundancy = 'none' if active <= 1 else ('at-risk' if available <= 1 else 'redundant')
        rows.append({'serviceId': s['service_id'], 'name': s['name'], 'capacityPercent': h.get('capacityPercent', 0),
                     'availableMembers': available, 'totalMembers': active, 'redundancyState': redundancy})
    return {'status': 'ok', 'services': rows}
