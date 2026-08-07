# Package 051 — Generic Stratum Live Activity Fix

Prevents configured or remembered Generic Stratum usernames from being treated as live mining sessions.

Changes:
- cumulative `acceptedShares` no longer proves current activity;
- generic worker relationships are inserted inactive unless live evidence exists;
- telemetry availability is propagated correctly;
- the existing worker-session and topology reconcilers remain authoritative.
