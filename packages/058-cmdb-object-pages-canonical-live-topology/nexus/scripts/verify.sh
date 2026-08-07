#!/usr/bin/env bash
set -euo pipefail
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$REPO"
python3 -m backend.jobs.platform_sync_job > /tmp/nexus-package-058-sync.json
python3 - <<'PY'
import json, urllib.request

def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8080"+path, timeout=10) as r:
        return json.load(r)
workers=get("/api/platform/workers")
topology=get("/api/platform/topology")
objects=get("/api/platform/objects")
active=[w for w in workers.get("workers",[]) if w.get("sourceSystem")=="seymour-native-stratum" and w.get("activityState")=="active"]
assert len(active) >= 2, f"Expected at least 2 active Seymour workers, got {len(active)}"
assert all(float(w.get("currentHashrate") or 0) >= 0 for w in active)
node_ids={n.get("id") for n in topology.get("nodes",[])}
assert "seymour-btc-solo" in node_ids, "Seymour operational pool missing"
assert "service-seymour-pool-engine-stratum" in node_ids, "Seymour engine service missing"
edge_types={e.get("type") for e in topology.get("edges",[])}
assert "served-by" in edge_types, "Pool-to-engine relationship missing"
assert "uses-blockchain-node" in edge_types, "Engine-to-node relationship missing"
service_objects=[o for o in objects.get("objects",[]) if o.get("objectType")=="service"]
assert service_objects, "CMDB service objects missing"
print(f"PASS: active Seymour workers {len(active)}")
print(f"PASS: topology nodes {len(node_ids)}")
print(f"PASS: CMDB service objects {len(service_objects)}")
PY
for path in /assets.html /cmdb-object.html /graph.html /api/platform/topology /api/platform/objects; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8080$path")"
  test "$code" = "200" || { echo "FAIL: $path HTTP $code"; exit 1; }
  echo "PASS: $path"
done
echo "Verify PASS"
