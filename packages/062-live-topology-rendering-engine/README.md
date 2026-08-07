# Package 062 — Live Topology Rendering Engine

Makes the Infrastructure Canvas render canonical current mining relationships in Live mode.

## Changes

- Normalizes relationship names such as `mines-on` and `MINES_ON`.
- Removes persisted/historical mining paths from the Live Canvas.
- Rebuilds exactly one `MINES_ON` path per physical asset from workers where `currentSession=true`.
- Uses canonical `assetId` and `poolInstanceId` values.
- Keeps historical paths available in Infrastructure Time Machine replay mode.
- Carries live hashrate and activity metadata on synthesized mining edges.

## Expected behavior

Mining System 2, CPU Mining VM, and every other active worker render against the pool owned by their current live session. Old CKPool or MiningCore relationships are not drawn in Live mode.
