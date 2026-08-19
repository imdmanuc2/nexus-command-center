# Package 076 — Managed Host Runtime Topology Reconciliation

## Purpose

Connect managed-host discovery evidence to the Nexus CMDB topology model.

This package establishes explicit operational relationships between:

- managed hosts
- blockchain node runtimes
- storage resources

## Canonical relationships

- blockchain-node `hosted-on` host
- blockchain-node `uses-storage` storage
- host `mounts` storage

## Design rules

- Preserve existing CMDB asset IDs.
- Do not create duplicate blockchain-node assets.
- Relationships are derived from operational evidence.
- The frontend does not infer topology.
- Reconciliation is idempotent.
- Stale relationships owned by this reconciliation source are deactivated.
- Existing pool-to-blockchain relationships remain unchanged.

## Reconciliation source

`managed-host-runtime-topology`

## Safety

This package does not execute remote lifecycle operations.

SSH managed-host enrollment is separate from CMDB topology reconciliation.
