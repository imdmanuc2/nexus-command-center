from backend.services.metrics_service import summary,current,history,rollups
def metrics_summary(): return summary()
def current_metrics(): return current()
def metric_history(): return history()
def metric_rollups(): return rollups()
