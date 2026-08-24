# SBP-075.7 — Nexus Provider-Neutral Blockchain Node Projection Repair

## Purpose

Repair the Nexus Seymour registration projection so blockchain nodes no longer
inherit Bitcoin Cash-specific implementation defaults.

## Changes

- Resolve implementation from:
  1. telemetry implementation when supplied
  2. canonical blockchain provider catalog
  3. provider-neutral fallback
- Resolve operational status from:
  1. explicit asset status
  2. telemetry lifecycleStatus
  3. telemetry runtimeState
  4. telemetry running boolean
  5. telemetry installed boolean
  6. unknown
- Apply identical status semantics to live metric projection.
- Preserve providerId and appId metadata.
- Add regression tests for Bitcoin, Bitcoin Cash, and Monero.
- Leave `/api/platform/inventory` contract unchanged.
- Do not modify frontend/UI.

## Expected mappings

| Provider | Coin | Implementation |
|---|---|---|
| bitcoin-mainnet | BTC | Bitcoin Core |
| bitcoin-cash-mainnet | BCH | Bitcoin Cash Node |
| monero-mainnet | XMR | Monero |

## Safety

The installer creates backups before modifying repository source files.
Rollback restores those backups.
