# Design Notes

The Infrastructure Explorer is a presentation layer over the reconciled PostgreSQL Platform model.

Canonical read flow:

```text
/api/platform/topology -> NexusExplorerPlatform.getTopology() -> graph.js
/api/platform/workers  -> NexusExplorerPlatform.getWorkers()  -> graph.js
```

The helper module normalizes Platform records for the existing Explorer rendering model. It no longer overrides `window.fetch`, which makes endpoint use explicit and debugging predictable.

`/api/graph/rebuild` remains only as an explicit reconciliation action. After that action, the displayed topology is fetched again from `/api/platform/topology`.
