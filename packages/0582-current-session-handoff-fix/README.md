# Package 058.2 — Current Session Handoff Fix

Fixes the PostgreSQL unique-constraint failure that occurs when a live Seymour
session is matched to a physical asset whose previous MiningCore or CKPool
session is still marked current.

The repository now atomically retires the previous current session before
binding the new live session. The normal reconciliation pass then confirms the
winning session and retires stale relationships.
