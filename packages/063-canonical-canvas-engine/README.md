# Package 063 — Canonical Canvas Engine

Makes the live Infrastructure Canvas a pure renderer of `/api/platform/topology`.

## Changes

- Removes client-side reconstruction of `MINES_ON` relationships from workers.
- Renders active canonical topology edges directly.
- Excludes inactive/stale relationships from Live mode.
- Preserves recorded edges in Infrastructure Time Machine snapshots.
- Adds a `graph.js?v=063` cache-buster to ensure browsers load the deployed renderer.
