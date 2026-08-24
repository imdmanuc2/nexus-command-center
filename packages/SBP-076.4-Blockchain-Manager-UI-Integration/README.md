# SBP-076.4 — Blockchain Manager UI Integration

## Purpose

Integrate the Blockchain page with the canonical provider-neutral
blockchain operational-state contract established by SBP-076.3.

## Changes

- Use the shared Nexus page shell.
- Rename Managed Nodes summary to Blockchain Runtimes.
- Distinguish Seymour-managed runtimes from independently discovered nodes.
- Treat `online` as an operational/running state.
- Preserve syncing progress.
- Generate provider filters dynamically from the provider catalog.
- Remove hard-coded BTC/BCH/XMR filter assumptions.
- Keep the provider catalog deployment-neutral.
- Preserve CMDB and Operations navigation.
