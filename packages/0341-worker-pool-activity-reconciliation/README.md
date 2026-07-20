# 0341 Worker Pool Activity Reconciliation

Corrects stale worker/workload pool state at the PostgreSQL reconciliation layer.

## Changes

- Keeps one current worker session per physical asset.
- Synchronizes workload pool fields to the winning worker session.
- Deactivates old workload `uses-pool` relationships.
- Deactivates non-canonical stale `mines-on` relationships.
- Preserves historical observations without presenting them as live topology.

This package does not manufacture activity. A miner appears active only when current telemetry or a confirmed live session exists.
