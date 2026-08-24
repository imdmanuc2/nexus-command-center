# SBP-076.3 — Canonical Blockchain Operational State

Repairs provider-neutral blockchain operational-state projection.

## Purpose

Nexus receives blockchain state from multiple valid providers:

- Seymour Blockchain Manager runtime telemetry
- native/legacy blockchain discovery
- RPC-backed blockchain node telemetry

The Operations API must normalize these sources without allowing stale
`blockchain_nodes.status` values or placeholder `sync_status=unknown`
values to override stronger current runtime evidence.

## State precedence

1. explicit `running=0` -> stopped
2. IBD + reachable RPC -> syncing
3. running + healthy RPC -> running
4. running runtime -> running
5. meaningful sync status
6. meaningful node status
7. legacy/native RPC connection -> online
8. unknown

No asset identities or relationships are modified.
