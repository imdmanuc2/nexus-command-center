# Package 062.1 — Canonical Canvas Renderer

This package makes the Live Infrastructure Canvas render canonical current topology only and corrects live pool-card state.

## Changes

- Live mode uses current-session worker assignments as the only `MINES_ON` authority.
- Inactive and stale relationships remain available to Infrastructure Time Machine but cannot render as live paths.
- Mining pool cards derive status and hashrate from current, non-stale workers assigned to the exact pool instance.
- Active pools display `ACCEPTING · <hashrate>` instead of `IDLE`.
- CKPool, MiningCore, and Seymour pool instances remain isolated by canonical pool-instance ID.
