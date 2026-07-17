
# Package 022 — Worker Identity & Activity Reconciliation

Establishes one authoritative current-worker model for Fleet, Home V2,
Topology, AI Context, Recommendations, Alerts, and Infrastructure Explorer.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Key behavior

- Generic Stratum remembered usernames remain `unknown` without live evidence.
- Offline, stale, and unknown workers have zero current metrics.
- One current worker session is selected per physical asset.
- Losing pool sessions become stale and their worker relationships inactive.
- Fleet, Context, Recommendations, and Topology consume active workers only.
