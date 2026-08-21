# Package 080 — Blockchain Operations Surface

## Purpose

Create the first dedicated Nexus Blockchain operations page.

The page presents canonical blockchain runtime state already reconciled
into Nexus.

## Source of Truth

The page must not independently probe blockchain runtimes.

State precedence:

1. Canonical `nexus.blockchain_nodes`
2. Canonical `nexus.current_metrics`
3. CMDB asset state
4. Unknown fallback

The Seymour Blockchain Manager remains responsible for runtime-specific
discovery, telemetry and lifecycle management.

Nexus remains the fleet-level management surface.

## Initial Scope

- Dedicated `/blockchain.html`
- Primary navigation entry
- Blockchain summary
- Per-node runtime state
- Sync progress
- Block/header heights
- Peer count
- RPC state
- Management relationship
- Link to CMDB Digital Twin

Lifecycle mutations are intentionally deferred until the read-only
contract is verified.
