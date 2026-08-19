# Package 074 — Blockchain Management Foundation

Establishes Nexus Command Center as the canonical blockchain
management control plane.

## Scope

Package 074 provides:

- provider-neutral blockchain catalog
- BTC, BCH, and Monero provider definitions
- storage selection contract
- custom storage path contract
- configurable P2P/RPC ports
- host selection contract
- deployment-plan validation
- architecture requirements
- preflight result model

Package 074 deliberately does not execute installations.

No Docker lifecycle, Umbrel lifecycle, filesystem mutation, package
installation, or arbitrary remote shell execution is introduced.

## Product direction

Nexus Command Center is the primary management platform.

Umbrel applications may remain discovery/catalog entry points, but
blockchain installation and lifecycle management will move behind the
Nexus control plane.

Future packages will connect this planning contract to managed-host
discovery, storage discovery, port validation, preflight checks,
deployment execution, lifecycle management, and entitlement policy.

## Canonical inventory rule

The Nexus CMDB is the canonical source of truth for managed infrastructure.

Blockchain discovery, runtime telemetry, registration payloads, managed-host
transport, storage discovery, and lifecycle observers are evidence sources.
They must reconcile their findings into the CMDB rather than create competing
inventory systems.

Future blockchain installation-state, host association, storage association,
and runtime relationship APIs will therefore be projected from canonical CMDB
objects and relationships.

Package 074 intentionally does not infer missing host relationships from
container names, laboratory IP addresses, Umbrel application state, or other
environment-specific assumptions.
