# Package 083 — Monero Managed Runtime Installation

## Purpose

Install the canonical Seymour Monero mainnet runtime under Nexus orchestration.

Nexus runs on the management host and connects to the canonical Umbrel runtime
host through the managed-host SSH transport.

The actual blockchain application installation uses the existing Seymour
Umbrel native lifecycle adapter. Package 083 does not bypass Umbrel with an
independent Docker deployment path.

## Runtime

Provider:

    monero-mainnet

Umbrel app:

    seymour-monero-node

Canonical image:

    ghcr.io/imdmanuc2/seymour-monero-node:0.18.5.1

Runtime host:

    asset-host-be24584e412bf6f6

Storage visible from runtime host:

    /mnt/seymour-storage/monero-mainnet

Physical storage resides on the separately managed storage infrastructure.

## Safety

Execution requires:

    INSTALL-SEYMOUR-MONERO

Before execution Package 081 must report:

    status = ready
    ready  = true
    blockers = []

Package 083 refuses installation when an existing Monero runtime is detected.

## Installation path

Nexus invokes the existing remote adapter:

    scripts/seymour-install-monero
        --execute
        --confirm INSTALL-seymour-monero-node

That adapter delegates to the Seymour native Umbrel lifecycle bridge.

## Scope

Package 083 installs and verifies the runtime.

CMDB runtime/telemetry reconciliation is a following milestone.
