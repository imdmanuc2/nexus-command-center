# Package 064 — Operational State Completion

Makes the Nexus Operational State Engine authoritative for mining-pool state.

## Changes

- Derives canonical pool state from reachability, current workers, and live hashrate.
- Publishes `accepting-shares`, `hashrate-stabilizing`, `online`, `degraded`, or `offline` through topology.
- Adds canonical pool hashrate and worker count to pool nodes.
- Makes the Canvas prefer canonical pool state and telemetry over a client-side `IDLE` fallback.
- Applies the behavior generically to Seymour, CKPool, MiningCore, and future pool engines.
