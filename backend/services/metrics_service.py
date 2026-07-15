from backend.db.repositories.telemetry_repository import (
    telemetry_summary,list_current_metrics,list_metric_history,list_rollups)

def summary():
    return {"status":"ok","source":"nexus-postgresql-telemetry",**telemetry_summary()}
def current():
    rows=list_current_metrics()
    return {"status":"ok","source":"nexus-postgresql-telemetry","count":len(rows),"metrics":rows}
def history():
    rows=list_metric_history()
    return {"status":"ok","source":"nexus-postgresql-telemetry","hours":24,"count":len(rows),"metrics":rows}
def rollups():
    rows=list_rollups()
    return {"status":"ok","source":"nexus-postgresql-telemetry","bucketSize":"1h","hours":168,"count":len(rows),"metrics":rows}
