# Package 073.1 — Post-Mission-Control Stability Cleanup

## Purpose

Checkpoint stability fixes discovered immediately after Package 073
Mission Control.

## Scope

- Support cache-busting query parameters on static CSS/JavaScript requests.
- Reopen previously resolved alerts when their condition recurs.
- Reopen previously completed/dismissed recommendations when regenerated.
- Avoid unnecessary maintenance-window lookups for platform events that
  do not match enabled alert rules.
- Cache maintenance suppression state per entity during one alert-engine pass.

## Safety

This package does not modify CMDB data, graph layout state, blockchain
runtimes, managed hosts, mining pools, or workers.
