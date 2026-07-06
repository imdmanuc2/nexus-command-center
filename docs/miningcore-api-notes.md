# MiningCore API Notes

## Pool Summary
GET /api/pools/bch

Returns:
- poolStats.connectedMiners
- poolStats.poolHashrate
- poolStats.sharesPerSecond
- networkStats.networkHashrate
- networkStats.networkDifficulty
- networkStats.blockHeight
- networkStats.connectedPeers
- topMiners
- totalBlocks
- poolEffort

## Miner Detail
GET /api/pools/bch/miners/<wallet>

Returns:
- pendingShares
- pendingBalance
- totalPaid
- todayPaid
- performance.workers
- performanceSamples

Worker fields:
- hashrate
- sharesPerSecond

This is the endpoint Nexus uses for individual ASIC worker stats.
