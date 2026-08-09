# SBP-029 — Nexus CMDB Blockchain Runtime State UI

Target repository:

    /home/imdmanuc/Projects/Seymour/nexus-command-center

Purpose:

- surface the normalized blockchain runtime state proven by SBP-028 in the Nexus CMDB UI;
- preserve existing CMDB page layout and behavior;
- add a self-contained runtime-state card to blockchain-node object detail pages;
- decorate visible CMDB asset links/cards with a compact runtime-state badge where possible;
- show sync progress, RPC reachability/health, IBD state, state reason, and last-seen time;
- consume the existing `/api/cmdb/assets` contract without adding a new backend API.

This package intentionally avoids rewriting `assets.js` or `cmdb-object.js`. It installs a
small additive UI module and stylesheet, then wires them into the two existing CMDB pages.
