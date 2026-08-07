# Package 045 — Change Management & Controlled Operations

Package 045 introduces the Nexus controlled-change lifecycle and connects approved changes to the existing shared Operations Engine queue.

## Included

- Change templates
- Change requests
- Approval history
- Execution steps and immutable execution log
- Dependency impact snapshots
- Maintenance-window enforcement
- Approval, execute, complete, fail, cancel, and rollback APIs
- Queue handoff to `nexus.operation_queue`
- Operations Center change-management UI
- Strict live endpoint verification

## Safety boundary

This package never runs arbitrary shell commands from the browser. Execution is handed to the existing allow-listed capability and Operations Engine infrastructure. Creating or approving a change does not bypass capability validation.


## Revision 2 compatibility

Revision 2 removes the hard PostgreSQL foreign-key dependency on
`nexus.operation_queue`.

When the shared Operations Queue exists, approved changes and rollbacks are
queued normally. When it does not exist, the change remains approved (or
rollback-pending), the event is recorded, and execution is safely deferred
until the Operations Engine is installed.


## Revision 3

Revision 3 corrects the `do_POST` route insertion so change-management and maintenance routes are structurally valid Python and compile before service restart.


## Revision 4 compatibility

Revision 4 adds a bounded JSON request-body parser directly to `NexusHandler`.
This makes the change-management POST routes compatible with the current Nexus
HTTP server implementation while preserving its existing response behavior.
