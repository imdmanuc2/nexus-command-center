# Design

The worker session reconciler is the authority for current worker activity. Historical rows and observations remain queryable, but only a worker with `current_session = TRUE` and activity `active` or `idle` may retain operational workload and pool relationships.

The topology reconciliation service remains responsible for publishing the canonical active asset-to-pool `mines-on` edge.
