from backend.db.repositories import intelligence_repository as repo
from backend.core import impact_engine, root_cause_engine, recommendation_engine

def _q(query, key, default=''):
    return (query.get(key) or [default])[0]

def knowledge(query):
    return {'status':'ok','items':repo.knowledge(_q(query,'assetType') or None,_q(query,'issueCode') or None)}

def analyze(query):
    asset_id = _q(query, 'assetId')
    if not asset_id:
        raise ValueError('assetId is required')
    rels = repo.relationships()
    ids = {asset_id}
    for rel in rels:
        ids.add(rel['source_id']); ids.add(rel['target_id'])
    assets = {item: repo.asset(item) for item in ids}
    asset = assets[asset_id]
    impact = impact_engine.analyze(asset_id, rels)
    root = root_cause_engine.analyze(asset, rels, assets)
    asset_type = str(asset.get('asset_type') or asset.get('type') or 'compute').lower()
    issue_code = _q(query, 'issueCode') or ('asset-offline' if str(asset.get('status','')).lower() in {'offline','failed','critical'} else None)
    kb = repo.knowledge(asset_type, issue_code)
    if not kb:
        kb = repo.knowledge('compute', 'asset-offline')
    recs = recommendation_engine.recommend(asset, kb, root)
    return {'status':'ok','source':'nexus-intelligence','asset':asset,'rootCause':root,'impact':impact,'recommendations':recs,'knowledge':kb[:3]}
