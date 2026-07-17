from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def write_metrics(metrics: Iterable[dict[str, Any]]) -> int:
    rows = list(metrics)
    now = datetime.now(timezone.utc)
    if not rows:
        return 0
    with transaction() as conn:
        with conn.cursor() as cur:
            for m in rows:
                p = {
                    "observed_at": m.get("observedAt") or now,
                    "entity_type": str(m["entityType"]),
                    "entity_id": str(m["entityId"]),
                    "metric_name": str(m["metricName"]),
                    "metric_value": float(m["metricValue"]),
                    "metric_unit": str(m.get("metricUnit") or ""),
                    "status": str(m.get("status") or ""),
                    "source": str(m.get("source") or "nexus-telemetry"),
                    "labels": Jsonb(m.get("labels") or {}),
                    "metadata": Jsonb(m.get("metadata") or {}),
                }
                cur.execute("""INSERT INTO nexus.metric_samples(
                    observed_at,entity_type,entity_id,metric_name,metric_value,
                    metric_unit,status,source,labels,metadata)
                    VALUES(%(observed_at)s,%(entity_type)s,%(entity_id)s,%(metric_name)s,
                    %(metric_value)s,%(metric_unit)s,%(status)s,%(source)s,%(labels)s,%(metadata)s)""", p)
                cur.execute("""INSERT INTO nexus.metric_current(
                    entity_type,entity_id,metric_name,metric_value,metric_unit,status,
                    source,labels,metadata,observed_at,updated_at)
                    VALUES(%(entity_type)s,%(entity_id)s,%(metric_name)s,%(metric_value)s,
                    %(metric_unit)s,%(status)s,%(source)s,%(labels)s,%(metadata)s,%(observed_at)s,NOW())
                    ON CONFLICT(entity_type,entity_id,metric_name) DO UPDATE SET
                    metric_value=EXCLUDED.metric_value,metric_unit=EXCLUDED.metric_unit,
                    status=EXCLUDED.status,source=EXCLUDED.source,labels=EXCLUDED.labels,
                    metadata=EXCLUDED.metadata,observed_at=EXCLUDED.observed_at,updated_at=NOW()""", p)
    return len(rows)

def list_current_metrics(limit: int = 1000) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM nexus.metric_current
                           ORDER BY entity_type,entity_id,metric_name LIMIT %s""",
                        (max(1,min(limit,5000)),))
            rows = cur.fetchall()
    return [{
        "entityType":r["entity_type"],"entityId":r["entity_id"],
        "metricName":r["metric_name"],"metricValue":r["metric_value"],
        "metricUnit":r["metric_unit"],"status":r["status"],"source":r["source"],
        "labels":r["labels"] or {},"metadata":r["metadata"] or {},
        "observedAt":r["observed_at"].isoformat()
    } for r in rows]

def list_metric_history(hours: int = 24, limit: int = 5000) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM nexus.metric_samples
                           WHERE observed_at >= NOW()-(%s*INTERVAL '1 hour')
                           ORDER BY observed_at DESC LIMIT %s""",
                        (max(1,min(hours,8760)),max(1,min(limit,20000))))
            rows = cur.fetchall()
    return [{
        "sampleId":r["sample_id"],"observedAt":r["observed_at"].isoformat(),
        "entityType":r["entity_type"],"entityId":r["entity_id"],
        "metricName":r["metric_name"],"metricValue":r["metric_value"],
        "metricUnit":r["metric_unit"],"status":r["status"],"source":r["source"],
        "labels":r["labels"] or {},"metadata":r["metadata"] or {}
    } for r in rows]

def list_rollups(bucket_size: str="1h", hours: int=168, limit: int=5000):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM nexus.metric_rollups
                           WHERE bucket_size=%s
                           AND bucket_start >= NOW()-(%s*INTERVAL '1 hour')
                           ORDER BY bucket_start DESC LIMIT %s""",
                        (bucket_size,max(1,min(hours,43800)),max(1,min(limit,20000))))
            rows = cur.fetchall()
    return [{
        "bucketStart":r["bucket_start"].isoformat(),"bucketSize":r["bucket_size"],
        "entityType":r["entity_type"],"entityId":r["entity_id"],
        "metricName":r["metric_name"],"metricUnit":r["metric_unit"],
        "sampleCount":r["sample_count"],"minimumValue":r["minimum_value"],
        "maximumValue":r["maximum_value"],"averageValue":r["average_value"],
        "sumValue":r["sum_value"],"lastValue":r["last_value"],
        "labels":r["labels"] or {}
    } for r in rows]

def build_rollups(bucket_size: str) -> int:
    expr = {"1m":"date_trunc('minute',observed_at)",
            "1h":"date_trunc('hour',observed_at)",
            "1d":"date_trunc('day',observed_at)"}.get(bucket_size)
    if not expr: raise ValueError(bucket_size)
    lookback = {"1m":"2 hours","1h":"3 days","1d":"90 days"}[bucket_size]
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""INSERT INTO nexus.metric_rollups(
                bucket_start,bucket_size,entity_type,entity_id,metric_name,metric_unit,
                sample_count,minimum_value,maximum_value,average_value,sum_value,last_value,labels,updated_at)
                SELECT {expr},%s,entity_type,entity_id,metric_name,MAX(metric_unit),COUNT(*),
                MIN(metric_value),MAX(metric_value),AVG(metric_value),SUM(metric_value),
                (ARRAY_AGG(metric_value ORDER BY observed_at DESC))[1],
                COALESCE((ARRAY_AGG(labels ORDER BY observed_at DESC))[1],'{{}}'::jsonb),NOW()
                FROM nexus.metric_samples WHERE observed_at>=NOW()-%s::interval
                GROUP BY {expr},entity_type,entity_id,metric_name
                ON CONFLICT(bucket_start,bucket_size,entity_type,entity_id,metric_name)
                DO UPDATE SET sample_count=EXCLUDED.sample_count,minimum_value=EXCLUDED.minimum_value,
                maximum_value=EXCLUDED.maximum_value,average_value=EXCLUDED.average_value,
                sum_value=EXCLUDED.sum_value,last_value=EXCLUDED.last_value,
                labels=EXCLUDED.labels,updated_at=NOW()""",(bucket_size,lookback))
            return cur.rowcount

def apply_retention():
    result={}
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nexus.metric_samples WHERE observed_at<NOW()-INTERVAL '30 days'")
            result["rawSamples"]=cur.rowcount
            for size,days,key in (("1m",90,"minuteRollups"),("1h",730,"hourlyRollups"),("1d",3650,"dailyRollups")):
                cur.execute("""DELETE FROM nexus.metric_rollups
                               WHERE bucket_size=%s AND bucket_start<NOW()-(%s*INTERVAL '1 day')""",(size,days))
                result[key]=cur.rowcount
    return result

def telemetry_summary():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) metric_count,
                           COUNT(DISTINCT entity_type||':'||entity_id) entity_count,
                           MAX(observed_at) latest FROM nexus.metric_current""")
            current=cur.fetchone()
            cur.execute("SELECT COUNT(*) sample_count FROM nexus.metric_samples")
            samples=cur.fetchone()
            cur.execute("SELECT bucket_size,COUNT(*) count FROM nexus.metric_rollups GROUP BY bucket_size")
            rollups=cur.fetchall()
    return {"currentMetricCount":current["metric_count"],"entityCount":current["entity_count"],
            "latestObservation":current["latest"].isoformat() if current["latest"] else None,
            "sampleCount":samples["sample_count"],
            "rollups":{r["bucket_size"]:r["count"] for r in rollups}}
