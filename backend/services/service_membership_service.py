from __future__ import annotations

import hashlib
import uuid

from backend.db.repositories import service_membership_repository as repo


def _norm(value):
    return str(value or '').strip().lower()


def _haystack(asset):
    values = [
        asset.get('asset_type'), asset.get('canonical_type'), asset.get('name'),
        asset.get('friendly_name'), asset.get('display_name'), asset.get('purpose'),
        asset.get('primary_role'), asset.get('coin'), asset.get('business_service'),
        asset.get('compute_kind'),
    ]
    return ' | '.join(_norm(v) for v in values)


def _matches(rule, asset):
    definition = rule.get('match_definition') or {}
    workload_terms = {_norm(v) for v in definition.get('workloadCategories', [])}
    asset_workloads = {_norm(v) for v in asset.get('workload_categories', [])}
    if workload_terms and workload_terms.intersection(asset_workloads):
        return True, 'workload-category'

    coins = {_norm(v) for v in definition.get('coins', [])}
    if coins and _norm(asset.get('coin')) in coins:
        return True, 'coin'

    text = _haystack(asset)
    for term in definition.get('textTerms', []):
        if _norm(term) and _norm(term) in text:
            return True, 'asset-classification'
    return False, ''


def reconcile(trigger_source='manual'):
    run_id = f"bsr-{uuid.uuid4().hex}"
    counters = {
        'assetsEvaluated': 0, 'membershipsMatched': 0,
        'membershipsCreated': 0, 'membershipsUpdated': 0,
        'membershipsRetired': 0,
    }
    repo.start_run(run_id, trigger_source)
    try:
        rules = repo.rules()
        assets = repo.candidates()
        counters['assetsEvaluated'] = len(assets)
        selected = {}
        for asset in assets:
            for rule in rules:
                matched, reason = _matches(rule, asset)
                if not matched:
                    continue
                key = (rule['service_id'], asset['asset_id'])
                current = selected.get(key)
                if current and int(current['priority']) <= int(rule['priority']):
                    continue
                selected[key] = {
                    'service_id': rule['service_id'], 'asset_id': asset['asset_id'],
                    'role': rule['role'], 'required': bool(rule['required']),
                    'priority': int(rule['priority']), 'rule_id': rule['rule_id'],
                    'reason': reason,
                }

        for match in selected.values():
            digest = hashlib.md5(
                f"{match['service_id']}:{match['asset_id']}:{match['role']}".encode(),
                usedforsecurity=False,
            ).hexdigest()
            payload = {
                **match,
                'membership_id': f'bsm-{digest}',
                'confidence': 98 if match['reason'] == 'workload-category' else 90,
                'metadata': {'ruleId': match['rule_id'], 'matchReason': match['reason']},
            }
            inserted = repo.upsert_membership(payload, run_id)
            counters['membershipsMatched'] += 1
            counters['membershipsCreated' if inserted else 'membershipsUpdated'] += 1

        counters['membershipsRetired'] = repo.retire_unmatched(run_id)
        repo.finish_run(run_id, 'completed', counters)
        return {'status':'ok','runId':run_id,**counters}
    except Exception as exc:
        repo.finish_run(run_id, 'failed', counters, str(exc))
        raise


def rules(_query=None):
    return {'status':'ok','rules':repo.rules()}


def runs(query=None):
    query = query or {}
    limit = (query.get('limit') or ['25'])[0]
    return {'status':'ok','runs':repo.runs(limit)}
