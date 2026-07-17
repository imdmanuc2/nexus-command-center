from __future__ import annotations
import json
from datetime import datetime, timezone
from urllib.request import urlopen
from backend.db.repositories.telemetry_repository import write_metrics

BASE="http://127.0.0.1:8080"

def fetch(path):
    with urlopen(BASE+path,timeout=15) as r:
        return json.loads(r.read().decode())

def metric(et,eid,name,value,unit="",status="",labels=None):
    try: value=float(value)
    except (TypeError,ValueError): return None
    return {"entityType":et,"entityId":eid,"metricName":name,"metricValue":value,
            "metricUnit":unit,"status":status,"source":"nexus-platform-telemetry-collector",
            "labels":labels or {},"observedAt":datetime.now(timezone.utc)}

def collect_metrics():
    workers=fetch("/api/platform/workers").get("workers",[])
    pools=fetch("/api/platform/pools").get("pools",[])
    fleet=fetch("/api/platform/fleet")
    out=[]
    for w in workers:
        wid=w.get("workerId")
        if not wid: continue
        status=str(w.get("status") or "unknown")
        labels={"workerType":w.get("workerType"),"coin":w.get("coin"),
                "poolInstanceId":w.get("poolInstanceId"),"assetId":w.get("assetId")}
        for n,v,u in (("hashrate",w.get("currentHashrate"),w.get("hashrateUnit") or "H/s"),
                      ("shares_per_second",w.get("sharesPerSecond"),"shares/s"),
                      ("accepted_shares",w.get("acceptedShares"),"shares"),
                      ("rejected_shares",w.get("rejectedShares"),"shares"),
                      ("online",1 if status.lower()=="online" else 0,"boolean")):
            x=metric("worker",wid,n,v,u,status,labels)
            if x: out.append(x)
    for p in pools:
        pid=p.get("poolId")
        if not pid: continue
        status=str(p.get("status") or "unknown")
        labels={"coin":p.get("coin"),"mode":p.get("mode"),"host":p.get("host")}
        for n,v,u in (("hashrate",p.get("currentHashrate"),"H/s"),
                      ("worker_count",p.get("workerCount"),"workers"),
                      ("online_worker_count",p.get("onlineWorkerCount"),"workers"),
                      ("online",1 if status.lower() in {"online","healthy","running"} else 0,"boolean")):
            x=metric("pool",pid,n,v,u,status,labels)
            if x: out.append(x)
    for n,v,u in (("fleet_health",fleet.get("fleetHealth"),"percent"),
                  ("fleet_hashrate",fleet.get("fleetHashrate"),fleet.get("hashrateUnit") or "H/s"),
                  ("worker_total",fleet.get("workers",{}).get("total"),"workers"),
                  ("worker_online",fleet.get("workers",{}).get("online"),"workers"),
                  ("pool_total",fleet.get("pools",{}).get("total"),"pools")):
        x=metric("fleet","primary",n,v,u,"current")
        if x: out.append(x)
    return out

def collect_and_store():
    return write_metrics(collect_metrics())
