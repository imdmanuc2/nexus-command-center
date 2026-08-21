# Package 082 — Managed Blockchain Privileged Runtime Helper

## Purpose

Provide Nexus Command Center with a narrowly scoped privilege boundary for
approved blockchain runtime operations on a managed host.

Package 082 does not install Monero or any other blockchain runtime.

## Security model

The Nexus managed SSH account remains unprivileged.

The account is NOT added to the Docker group.

The account is NOT granted unrestricted passwordless sudo.

A root-owned helper is installed:

    /usr/local/libexec/seymour-blockchain-runtime

The sudoers policy allows execution of only that helper:

    umbrel ALL=(root) NOPASSWD: /usr/local/libexec/seymour-blockchain-runtime *

The helper implements its own fixed operation allow-list.

Package 082 initially enables only read-only operations:

    info
    list

Mutating operations are intentionally deferred to a later package.

## Nexus capabilities

Package 082 adds:

    blockchain.runtime.info
    blockchain.runtime.list

These capabilities use the existing Nexus managed-host executor and SSH
transport contracts.

## Expected result

After Package 082 is installed, Nexus can safely inspect Docker runtime state
on the managed Umbrel host without granting the SSH account general Docker or
root access.
