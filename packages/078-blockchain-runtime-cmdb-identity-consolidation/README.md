# Package 078 — Blockchain Runtime CMDB Identity Consolidation

## Purpose

Consolidate historical Seymour Blockchain Manager and BCH runtime CMDB
identities after persistent producer identity has been established.

## Safety model

Planning is the default behavior.

Execution requires:

    --execute
    --confirm CONSOLIDATE-SEYMOUR-RUNTIME-IDENTITIES

The operation is transactional and rolls back on failed postconditions.

## Historical evidence policy

Historical evidence remains historical.

The package does not rewrite:

- Seymour registration raw payloads;
- Seymour registration result payloads;
- audit event metadata;
- platform context snapshots.

Audit event indexed asset references are reconciled to the canonical BCH
runtime so historical events remain discoverable from the canonical CMDB
object while original IDs remain preserved inside historical metadata.

## Live-state merge policy

- canonical Blockchain Manager asset survives;
- canonical BCH asset survives;
- canonical BCH `blockchain_nodes` projection survives;
- stale BCH projections are removed;
- `current_metrics` uses newest observation wins;
- stale Seymour `manages` relationships are removed;
- canonical Manager -> BCH relationship survives;
- stale Manager/BCH asset rows are removed only after reference migration.

Execution is prohibited when unexpected foreign-key references or unexpected
relationship types are detected.

## Verified live consolidation

Package 078 was executed against the live Nexus CMDB after persistent Seymour
Umbrel identity was established.

Result:

- assets: 37 -> 7
- relationships: 47 -> 32
- stale assets removed: 30
- stale BCH projections removed: 15
- stale Seymour relationships removed: 15
- stale current metrics removed: 247
- audit event indexed references reconciled: 5077
- historical Seymour registration rows preserved: 17

Canonical identities after consolidation:

    Manager: asset-7be2040a1a33c91c
    BCH:     asset-1a3a169d72207de3
    BTC:     asset-82ac3c36

Historical raw registration payloads, registration results, audit metadata,
and platform context snapshots remain unchanged.
