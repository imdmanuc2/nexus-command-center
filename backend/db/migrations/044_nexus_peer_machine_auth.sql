BEGIN;

ALTER TABLE nexus.nexus_peer_enrollments
    ADD COLUMN IF NOT EXISTS requested_public_key_algorithm TEXT,
    ADD COLUMN IF NOT EXISTS requested_public_key TEXT,
    ADD COLUMN IF NOT EXISTS requested_public_key_fingerprint TEXT;

ALTER TABLE nexus.nexus_peer_enrollments
    DROP CONSTRAINT IF EXISTS
        nexus_peer_enrollments_public_key_algorithm_check;

ALTER TABLE nexus.nexus_peer_enrollments
    ADD CONSTRAINT
        nexus_peer_enrollments_public_key_algorithm_check
    CHECK (
        requested_public_key_algorithm IS NULL
        OR requested_public_key_algorithm = 'Ed25519'
    );


ALTER TABLE nexus.nexus_peers
    ADD COLUMN IF NOT EXISTS public_key_algorithm TEXT,
    ADD COLUMN IF NOT EXISTS public_key TEXT,
    ADD COLUMN IF NOT EXISTS public_key_fingerprint TEXT;

ALTER TABLE nexus.nexus_peers
    DROP CONSTRAINT IF EXISTS nexus_peers_public_key_algorithm_check;

ALTER TABLE nexus.nexus_peers
    ADD CONSTRAINT nexus_peers_public_key_algorithm_check
    CHECK (
        public_key_algorithm IS NULL
        OR public_key_algorithm = 'Ed25519'
    );

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_nexus_peers_public_key_fingerprint
    ON nexus.nexus_peers(
        local_instance_id,
        public_key_fingerprint
    )
    WHERE public_key_fingerprint IS NOT NULL;

INSERT INTO public.schema_migrations (
    version,
    description
)
VALUES (
    '044',
    'Nexus peer Ed25519 machine authentication foundation'
)
ON CONFLICT(version) DO NOTHING;

COMMIT;
