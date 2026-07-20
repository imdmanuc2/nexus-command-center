# Home V2 Beta Audit — Initial Findings

## Already integrated

Home V2 already consumes the primary PostgreSQL Platform APIs:

- `/api/platform/home`
- `/api/platform/context/home`
- `/api/platform/events`
- `/api/platform/recommendations/high-priority`
- `/api/platform/metrics/history`
- `/api/platform/metrics/rollups`
- `/api/smc/health`

The current Home V2 layout should be preserved.

## Gap corrected by Package 032

The Recent Operations Activity feed still called:

- `/api/events/operations`

That endpoint is backed by the retired file-based operations event module. Package 032 moves the feed to:

- `/api/platform/timeline/latest`

The replacement endpoint reads the PostgreSQL `nexus.operations_timeline` table.

## Remaining beta work

1. Remove the Home compatibility fetch interceptor after all legacy callers are migrated.
2. Validate Operations Center coverage for playbooks, policies, live sessions, queue, and history.
3. Move Infrastructure Explorer to direct Platform API calls.
4. Verify Fleet, Pools, Nodes, Workers, and Assets pages use reconciled PostgreSQL data.
5. Complete beta release testing, installation documentation, and distribution packaging.
