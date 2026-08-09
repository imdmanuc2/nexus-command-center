# SBP-027 — Nexus CMDB Runtime State Ingestion

Target repository:

    /home/imdmanuc/Projects/Seymour/nexus-command-center

Purpose:

- ingest the SBP-026 normalized Seymour blockchain runtime state into Nexus;
- project runtime state as first-class `nexus.current_metrics`;
- update the BCH blockchain-node asset `observed_state` from the normalized runtime state;
- preserve the existing SBP-018 telemetry projection;
- support both first-time registrations and duplicate/idempotent refreshes;
- keep registration ingestion idempotent.

Projected current metrics:

- runtime.state
- runtime.rpc.reachable
- runtime.rpc.healthy
- runtime.initial_block_download
- runtime.verification_progress

The canonical asset state is taken from `runtimeState`, falling back to
`operationalState.state` when necessary.
