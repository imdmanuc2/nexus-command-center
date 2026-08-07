# Package 061.1 — Live Session Pool Precedence Fix

Corrects current pool assignment when a miner has a live Seymour Stratum
session but has not yet submitted its first accepted share.

## Behavior

- A recent, online Seymour session is current when its phase is connected,
  authorized, receiving-jobs, submitting-shares, hashrate-stabilizing, or stable.
- Current pool assignment is independent from measured hashrate.
- A live Seymour session outranks historical MiningCore and CKPool telemetry for
  the same physical CMDB asset.
- A connected miner without accepted shares is shown as CONNECTED rather than
  incorrectly shown as mining on its previous pool.
- Historical worker records and telemetry are retained but are not current.
