def recommend(asset, knowledge_items, root_cause):
    recommendations = []
    for item in knowledge_items:
        for action in item.get('recommended_actions') or []:
            record = dict(action) if isinstance(action, dict) else {'label': str(action)}
            record['confidence'] = round(min(99, float(item.get('base_confidence') or 70) * 0.7 + float(root_cause.get('confidence') or 50) * 0.3), 1)
            record['why'] = item.get('title')
            recommendations.append(record)
    recommendations.sort(key=lambda r: (r.get('priority', 99), -r.get('confidence', 0)))
    return recommendations[:6]
