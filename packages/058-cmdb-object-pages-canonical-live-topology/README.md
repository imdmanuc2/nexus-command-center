# Package 058 — CMDB Object Pages & Canonical Live Topology

Adds a native Seymour Pool Engine adapter and normalizes all mining engines
behind stable operational pool objects.

## Delivered
- Seymour API live polling on `192.168.1.169:8561`
- Current-session filtering (`online`, phase, recent activity/share)
- Stable operational pool identity (`seymour-btc-solo`)
- Worker, workload, pool and relationship reconciliation
- Engine-agnostic topology path:
  `miner -> operational pool -> mining engine -> blockchain node`
- Mining engine service nodes for Seymour, CKPool and MiningCore
- Richer CMDB object summaries and service objects
- Canvas support for mining-engine service objects
- Backup and rollback scripts
