BEGIN;

-- Package 044 extends the existing Package 032 maintenance foundation.
ALTER TABLE nexus.maintenance_targets
  DROP CONSTRAINT IF EXISTS maintenance_targets_target_type_check;

ALTER TABLE nexus.maintenance_targets
  ADD CONSTRAINT maintenance_targets_target_type_check
  CHECK (target_type IN
    ('asset','asset_type','site','rack','pool','cluster','tag','service'));

CREATE TABLE IF NOT EXISTS nexus.maintenance_history (
  history_id BIGSERIAL PRIMARY KEY,
  window_id UUID NOT NULL REFERENCES nexus.maintenance_windows(window_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK
    (event_type IN ('scheduled','started','completed','cancelled','updated')),
  actor TEXT NOT NULL DEFAULT 'nexus',
  message TEXT NOT NULL DEFAULT '',
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_maintenance_history_window
  ON nexus.maintenance_history(window_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_maintenance_targets_service
  ON nexus.maintenance_targets(target_value)
  WHERE target_type='service';

INSERT INTO nexus.maintenance_history(window_id,event_type,actor,message,details,occurred_at)
SELECT w.window_id,
       CASE
         WHEN w.status='cancelled' THEN 'cancelled'
         WHEN NOW() >= w.ends_at THEN 'completed'
         WHEN NOW() >= w.starts_at THEN 'started'
         ELSE 'scheduled'
       END,
       'package-044',
       'Imported existing maintenance window into maintenance history.',
       jsonb_build_object('source','maintenance-windows-backfill'),
       w.created_at
FROM nexus.maintenance_windows w
WHERE NOT EXISTS (
  SELECT 1 FROM nexus.maintenance_history h WHERE h.window_id=w.window_id
);

COMMIT;
