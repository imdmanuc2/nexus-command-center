BEGIN;

-- Durable progress for bounded replay of successful blockchain.install
-- execution evidence into canonical CMDB runtime authority.
--
-- This state controls reconciliation traversal only. It never authorizes
-- operation re-execution or target lifecycle activity.

CREATE TABLE IF NOT EXISTS nexus.blockchain_runtime_authority_reconciliation_state (
    engine_name TEXT PRIMARY KEY,
    phase TEXT NOT NULL DEFAULT 'dated'
        CHECK (phase IN ('dated', 'null')),
    after_completed_at TIMESTAMPTZ,
    after_operation_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (
            phase = 'dated'
            AND (
                (
                    after_completed_at IS NULL
                    AND after_operation_id IS NULL
                )
                OR
                (
                    after_completed_at IS NOT NULL
                    AND after_operation_id IS NOT NULL
                    AND after_operation_id <> ''
                )
            )
        )
        OR
        (
            phase = 'null'
            AND after_completed_at IS NULL
        )
    )
);

COMMENT ON TABLE nexus.blockchain_runtime_authority_reconciliation_state IS
    'Durable bounded replay checkpoint for successful blockchain.install authority projection reconciliation.';

COMMENT ON COLUMN nexus.blockchain_runtime_authority_reconciliation_state.phase IS
    'Replay phase: dated completed_at rows or legacy NULL completed_at rows.';

COMMENT ON COLUMN nexus.blockchain_runtime_authority_reconciliation_state.after_completed_at IS
    'Exclusive completed_at keyset cursor for dated replay; NULL at phase start or during NULL phase.';

COMMENT ON COLUMN nexus.blockchain_runtime_authority_reconciliation_state.after_operation_id IS
    'Exclusive operation_id keyset cursor; paired with completed_at for dated replay and used alone for NULL replay.';

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '053',
    'Blockchain runtime authority reconciliation durable checkpoint'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
