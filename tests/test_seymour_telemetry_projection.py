from backend.db.repositories import seymour_telemetry_repository as repo

asset={
  "assetId":"asset-live-bch-test",
  "assetType":"blockchain-node",
  "coin":"BCH",
  "network":"mainnet",
  "providerId":"bitcoin-cash-mainnet",
  "status":"not-installed",
  "telemetry":{
    "running":False,
    "installed":False,
    "rpc":{"reachable":False},
    "data":{"usedBytes":7109798674},
    "sync":{"height":None,"headers":None,"progressPercent":None,"initialBlockDownload":False},
    "peers":None,
    "mempool":None,
  },
  "sync":{
    "snapshot":{"height":None,"headers":None,"progress_percent":None,"peers":None},
    "blocksRemaining":None,
    "blocksPerSecond":None,
    "peerQuality":{"score":0},
    "stall":{"stalled":True},
  },
}

metrics={item["metric_name"]:item for item in repo.metric_candidates(asset)}

assert metrics["running"]["metric_value"]==0.0
assert metrics["installed"]["metric_value"]==0.0
assert metrics["rpc_reachable"]["metric_value"]==0.0
assert metrics["data_used_bytes"]["metric_value"]==7109798674.0
assert metrics["initial_block_download"]["metric_value"]==0.0
assert metrics["peer_quality_score"]["metric_value"]==0.0
assert metrics["sync_stalled"]["metric_value"]==1.0
assert "block_height" not in metrics
assert "sync_progress" not in metrics
assert "peer_count" not in metrics

print("SBP-018 telemetry mapping verification: PASS")
