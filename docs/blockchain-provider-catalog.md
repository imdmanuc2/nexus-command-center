# Blockchain Provider Catalog

## Ownership

The canonical Seymour blockchain provider catalog is owned by:

seymour-umbrel-app-store/shared/provider_catalog/providers.v1.json

Nexus Command Center is not a second catalog authority.

Nexus contains a committed projection at:

backend/data/config/blockchain_provider_catalog.json

The committed projection allows Nexus to build and run without a runtime
dependency on the Seymour Umbrel App Store repository.

## Synchronization

During Seymour development, the normal layout is sibling repositories:

Projects/Seymour/
  nexus-command-center/
  seymour-umbrel-app-store/

Check the Nexus projection for drift with:

python3 scripts/sync_blockchain_provider_catalog.py --check

Update the Nexus projection from the canonical catalog with:

python3 scripts/sync_blockchain_provider_catalog.py

A canonical catalog change is incomplete until the Nexus projection has
been regenerated, reviewed, tested, and committed when its generated
output changes.

## Build and Runtime Boundary

Nexus runtime consumes only its committed packaged projection.

Nexus does not fetch the app-store repository at runtime.

The Nexus container build therefore remains reproducible from the Nexus
repository alone.

## Provider Availability

Availability and selectability originate in the canonical provider catalog.

Nexus deployment planning must refuse providers that are not both:

- availability = live
- selectable = true

Coming Soon and Planned providers may be displayed but are not executable.

## Source of Truth

The provider catalog describes blockchain-provider capabilities.

The Nexus CMDB remains the canonical source of truth for actual managed
infrastructure, including hosts, storage, installed runtimes, and their
relationships.
