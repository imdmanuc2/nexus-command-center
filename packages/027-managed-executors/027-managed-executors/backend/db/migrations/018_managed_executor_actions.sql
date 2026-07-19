BEGIN;

INSERT INTO nexus.automation_actions(
    action_id,
    name,
    description,
    action_type,
    entity_type,
    risk_level,
    requires_approval,
    supports_dry_run,
    timeout_seconds,
    retry_limit,
    command_template,
    metadata
)
VALUES
(
    'bitcoin.check-sync',
    'Check Bitcoin Synchronization',
    'Verify RPC connectivity, block height, headers, IBD state, and synchronization progress.',
    'managed-executor',
    'blockchain-node',
    'low',
    FALSE,
    TRUE,
    30,
    1,
    '{"executor":"bitcoin","operation":"check-sync"}'::JSONB,
    '{"safe":true,"readOnly":true}'::JSONB
),
(
    'bitcoin.verify-wallet',
    'Verify Bitcoin Wallet',
    'Verify that a requested Bitcoin Core wallet is currently loaded.',
    'managed-executor',
    'blockchain-node',
    'low',
    FALSE,
    TRUE,
    30,
    1,
    '{"executor":"bitcoin","operation":"verify-wallet"}'::JSONB,
    '{"safe":true,"readOnly":true}'::JSONB
),
(
    'bitcoin.collect-diagnostics',
    'Collect Bitcoin Diagnostics',
    'Collect a read-only Bitcoin node diagnostics snapshot for Operations Center.',
    'managed-executor',
    'blockchain-node',
    'low',
    FALSE,
    TRUE,
    45,
    1,
    '{"executor":"bitcoin","operation":"collect-diagnostics"}'::JSONB,
    '{"safe":true,"readOnly":true}'::JSONB
),
(
    'linux.collect-diagnostics',
    'Collect Linux Diagnostics',
    'Reserved managed Linux diagnostics action. Transport is not enabled in Package 027.',
    'managed-executor',
    'server',
    'low',
    FALSE,
    TRUE,
    60,
    1,
    '{"executor":"linux","operation":"collect-diagnostics"}'::JSONB,
    '{"safeNoop":true}'::JSONB
),
(
    'asic.collect-diagnostics',
    'Collect ASIC Diagnostics',
    'Reserved managed ASIC diagnostics action. Transport is not enabled in Package 027.',
    'managed-executor',
    'worker',
    'low',
    FALSE,
    TRUE,
    60,
    1,
    '{"executor":"asic","operation":"collect-diagnostics"}'::JSONB,
    '{"safeNoop":true}'::JSONB
)
ON CONFLICT(action_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    action_type = EXCLUDED.action_type,
    entity_type = EXCLUDED.entity_type,
    risk_level = EXCLUDED.risk_level,
    requires_approval = EXCLUDED.requires_approval,
    supports_dry_run = EXCLUDED.supports_dry_run,
    timeout_seconds = EXCLUDED.timeout_seconds,
    retry_limit = EXCLUDED.retry_limit,
    command_template = EXCLUDED.command_template,
    metadata = EXCLUDED.metadata,
    enabled = TRUE,
    updated_at = NOW();

INSERT INTO public.schema_migrations(version, description)
VALUES('018', 'Managed executor framework and Bitcoin read-only actions')
ON CONFLICT(version) DO NOTHING;

COMMIT;
