# Package 047 R4 — Change Rollback Orchestration Recovery

## Purpose

Corrective revision for Package 047 after live verification exposed four issues:

1. The package root calculation patched the wrong repository.
2. `psql` command substitution returned command-status text with UUID values.
3. Verification raced the continuously running rollback worker.
4. The local transport verification target used an unauthorized host identifier.

## R4 correction

The lifecycle verification now uses the transport layer's reserved local Nexus identity:

- `assetId`: `nexus-local`
- `targetId`: `nexus-local`
- `transport`: `local`

It polls the database for the final state of the exact rollback plan instead of
assuming a manually launched worker will claim it.

## Scope

This is a corrective overlay for an installed Package 047 R3/R3.1 system. It
does not reinstall the Package 047 application source files or migration.

## Workflow

```bash
cd packages/047-change-rollback-orchestration-recovery-r4
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

Commit and push only after verification passes.
