# Changelog

- Retire an existing current worker session before assigning a new live session
  to the same physical asset.
- Mark the displaced session stale and zero its live metrics.
- Preserve historical records while satisfying
  `uq_workers_one_current_session_per_asset`.
