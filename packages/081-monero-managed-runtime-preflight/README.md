# Package 081 — Monero Managed Runtime Preflight

## Purpose

Validate all prerequisites required to install a managed Monero mainnet
runtime through Nexus Command Center.

This package performs no Monero installation.

## Canonical deployment target

Runtime host:

    asset-host-be24584e412bf6f6

The host is resolved through the Nexus managed-host transport profile.

Storage is expected to be available to the runtime host through:

    /mnt/seymour-storage/monero-mainnet

The physical storage server address is infrastructure evidence and is not
hard-coded into the Monero deployment contract.

## Preconditions

The preflight validates:

- canonical host resolution
- SSH transport availability
- host architecture support
- Docker availability
- Monero storage path
- storage writability
- minimum free capacity
- P2P port 18080 availability
- RPC port 18081 availability
- absence of an existing Monero runtime
- Monero provider catalog contract

## Safety

Package 081 is read-only with respect to runtime installation.

It may create and remove a temporary write-test file inside the already
approved Monero storage directory.

## Privileged execution finding

Live verification determined that the canonical Umbrel runtime host has Docker
installed and the Docker socket present, but the managed `umbrel` SSH account
does not have direct Docker daemon access and does not have unrestricted
passwordless sudo.

This is treated as a deployment blocker rather than weakening host security by
adding the managed user to the Docker group.

A subsequent package must provide a narrowly scoped, allow-listed privileged
execution capability for approved blockchain runtime operations.

## Package 082 integration

Package 082 establishes the approved privileged runtime inspection boundary.

Monero preflight therefore does not require the managed SSH account to have
direct Docker socket access. Docker daemon information and runtime inventory
are obtained through:

    sudo -n /usr/local/libexec/seymour-blockchain-runtime info
    sudo -n /usr/local/libexec/seymour-blockchain-runtime list

Direct membership in the Docker group remains prohibited.
