import express from 'express';
import fetch from 'node-fetch';
import dotenv from 'dotenv';
import crypto from 'crypto';
import fs from 'fs/promises';
import path from 'path';

dotenv.config();
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static('public'));

// ========= F2POOL API =========
app.get('/api/f2pool', async (req, res) => {
  const miner = req.query.miner || 'cryptohashboyz';

  try {
    const response = await fetch('https://api.f2pool.com/v2/hash_rate/info', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'F2P-API-SECRET': process.env.F2POOL_API_TOKEN,
      },
      body: JSON.stringify({
        mining_user_name: miner,
        currency: 'bitcoin',
      }),
    });

    const data = await response.json();

    if (!data.info) {
      return res.status(400).json({ error: 'Missing `info` in response', raw: data });
    }

    res.json(data);
  } catch (error) {
    console.error(`F2Pool error for ${miner}:`, error);
    res.status(500).json({ error: 'F2Pool API request failed' });
  }
});



// ViaBTC endpoint (account-wide balance)
app.get('/api/viabtc', async (req, res) => {
  try {
    const { VIABTC_API_KEY, VIABTC_SECRET_KEY, VIABTC_API_ID } = process.env;
    const endpoint = 'https://www.viabtc.com/api/v1/balance';
    const nonce = Date.now();
    const signString = `${VIABTC_API_ID}${nonce}${VIABTC_SECRET_KEY}`;
    const sign = crypto.createHash('sha256').update(signString).digest('hex');

    const headers = {
      'Content-Type': 'application/json',
      'X-ACCESS-KEY': VIABTC_API_KEY,
      'X-ACCESS-SIGN': sign,
      'X-ACCESS-NONCE': nonce.toString(),
      'X-ACCESS-ID': VIABTC_API_ID,
    };

    const response = await fetch(endpoint, { headers });
    const json = await response.json();

    if (json.code && json.code !== 0) {
      return res.status(400).json({ error: json.message || 'ViaBTC API error' });
    }

    res.json(json);
  } catch (error) {
    console.error('ViaBTC error:', error);
    res.status(500).json({ error: 'ViaBTC API request failed' });
  }
});

const CKPOOL_LOG_DIR = process.env.CKPOOL_LOG_DIR ||
  '/home/imdmanuc/Downloads/ckolivas-ckpool-bb7b0aebe08e/logs';
const CKPOOL_STALE_SECONDS = Number(process.env.CKPOOL_STALE_SECONDS || 180);

function parseHashrate(value) {
  if (value === null || value === undefined) return 0;
  const text = String(value).trim();
  if (!text || text === '0') return 0;
  const match = text.match(/^([0-9]+(?:\.[0-9]+)?)\s*([kKmMgGtTpPeE]?)$/);
  if (!match) return 0;
  const units = { '': 1, k: 1e3, m: 1e6, g: 1e9, t: 1e12, p: 1e15, e: 1e18 };
  return Number(match[1]) * units[match[2].toLowerCase()];
}

function toIso(epochSeconds) {
  const value = Number(epochSeconds || 0);
  return value > 0 ? new Date(value * 1000).toISOString() : null;
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, 'utf8'));
}

async function readPoolStatus() {
  const filePath = path.join(CKPOOL_LOG_DIR, 'pool', 'pool.status');
  const raw = await fs.readFile(filePath, 'utf8');
  const records = raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(JSON.parse);
  const summary = records[0] || {};
  const rates = records[1] || {};
  const shares = records[2] || {};
  const lastUpdate = Number(summary.lastupdate || 0);
  const ageSeconds = lastUpdate ? Math.max(0, Math.floor(Date.now() / 1000) - lastUpdate) : null;
  return {
    online: Boolean(lastUpdate && ageSeconds <= CKPOOL_STALE_SECONDS),
    runtimeSeconds: Number(summary.runtime || 0),
    lastUpdateAt: toIso(lastUpdate),
    ageSeconds,
    users: Number(summary.Users || 0),
    workers: Number(summary.Workers || 0),
    idle: Number(summary.Idle || 0),
    disconnected: Number(summary.Disconnected || 0),
    hashrate1m: parseHashrate(rates.hashrate1m),
    hashrate5m: parseHashrate(rates.hashrate5m),
    hashrate15m: parseHashrate(rates.hashrate15m),
    hashrate1h: parseHashrate(rates.hashrate1hr),
    acceptedShares: Number(shares.accepted || 0),
    rejectedShares: Number(shares.rejected || 0),
    sharesPerSecond1m: Number(shares.SPS1m || 0),
    bestShare: Number(shares.bestshare || 0),
  };
}

async function readWorkers() {
  const usersDir = path.join(CKPOOL_LOG_DIR, 'users');
  const entries = await fs.readdir(usersDir, { withFileTypes: true });
  const now = Math.floor(Date.now() / 1000);
  const workers = [];

  for (const entry of entries) {
    if (!entry.isFile() || entry.name.includes(' (Copy)')) continue;
    try {
      const user = await readJson(path.join(usersDir, entry.name));
      const lastShare = Number(user.lastshare || 0);
      const ageSeconds = lastShare ? Math.max(0, now - lastShare) : null;
      const hashrate1m = parseHashrate(user.hashrate1m);
      const connectedWorkers = Number(user.workers || 0);
      const online = Boolean(
        connectedWorkers > 0 &&
        hashrate1m > 0 &&
        lastShare > 0 &&
        ageSeconds <= CKPOOL_STALE_SECONDS
      );
      workers.push({
        sourceWorkerId: entry.name,
        online,
        connectionConfirmed: online,
        telemetryAvailable: true,
        currentHashrate: online ? hashrate1m : 0,
        hashrate1m,
        hashrate5m: parseHashrate(user.hashrate5m),
        hashrate1h: parseHashrate(user.hashrate1hr),
        connectedWorkers,
        acceptedShares: Number(user.shares || 0),
        rejectedShares: null,
        lastShareAt: toIso(lastShare),
        lastShareAgeSeconds: ageSeconds,
        bestShare: Number(user.bestshare || 0),
        authorisedAt: toIso(user.authorised),
        workerNames: Array.isArray(user.worker)
          ? user.worker.map(item => item.workername).filter(Boolean)
          : [],
      });
    } catch (error) {
      console.error(`CKPool telemetry read failed for ${entry.name}:`, error);
    }
  }

  return workers.sort((a, b) => a.sourceWorkerId.localeCompare(b.sourceWorkerId));
}

app.get('/api/ckpool/status', async (req, res) => {
  try {
    const [pool, workers] = await Promise.all([readPoolStatus(), readWorkers()]);
    res.json({
      status: 'ok',
      source: 'ckpool-local-files',
      generatedAt: new Date().toISOString(),
      staleSeconds: CKPOOL_STALE_SECONDS,
      pool,
      workers,
    });
  } catch (error) {
    console.error('CKPool telemetry error:', error);
    res.status(503).json({
      status: 'error',
      source: 'ckpool-local-files',
      error: 'CKPool telemetry unavailable',
    });
  }
});

app.get('/api/ckpool/workers', async (req, res) => {
  try {
    res.json({
      status: 'ok',
      source: 'ckpool-local-files',
      generatedAt: new Date().toISOString(),
      staleSeconds: CKPOOL_STALE_SECONDS,
      workers: await readWorkers(),
    });
  } catch (error) {
    console.error('CKPool worker telemetry error:', error);
    res.status(503).json({ status: 'error', error: 'CKPool worker telemetry unavailable' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
