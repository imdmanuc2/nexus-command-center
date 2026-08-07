BEGIN;
CREATE SCHEMA IF NOT EXISTS nexus;

CREATE TABLE IF NOT EXISTS nexus.seymour_registrations (
  registration_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL DEFAULT 'seymour-blockchain-manager',
  manager_asset_id TEXT,
  node_asset_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
  payload_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'received',
  raw_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  result JSONB NOT NULL DEFAULT '{}'::JSONB,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_seymour_registrations_received
  ON nexus.seymour_registrations(received_at DESC);

CREATE INDEX IF NOT EXISTS idx_seymour_registrations_status
  ON nexus.seymour_registrations(status,last_seen_at DESC);

INSERT INTO schema_migrations(version,description)
VALUES('038','Seymour Blockchain Manager registration receiver and CMDB ingestion')
ON CONFLICT(version) DO NOTHING;
COMMIT;
