#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
DB_NAME="${NEXUS_DB_NAME:-nexus_platform}"
DB_USER="${NEXUS_DB_USER:-nexus_app}"
DB_HOST="${NEXUS_DB_HOST:-127.0.0.1}"
DB_PORT="${NEXUS_DB_PORT:-5432}"
ENV_FILE="$PROJECT_ROOT/backend/data/private/cmdb.env"
MIGRATIONS_DIR="$PROJECT_ROOT/backend/db/migrations"

log(){ printf '\n==> %s\n' "$*"; }
die(){ printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ -d "$PROJECT_ROOT" ]] || die "Project root not found: $PROJECT_ROOT"
command -v psql >/dev/null || die "psql is required"
command -v openssl >/dev/null || die "openssl is required"
mkdir -p "$PROJECT_ROOT/backend/data/private"
chmod 700 "$PROJECT_ROOT/backend/data/private"

if [[ -f "$ENV_FILE" ]]; then
  log "Using existing database settings from $ENV_FILE"
  set -a
  source "$ENV_FILE"
  set +a
  DB_NAME="$NEXUS_DB_NAME"; DB_USER="$NEXUS_DB_USER"; DB_HOST="$NEXUS_DB_HOST"; DB_PORT="$NEXUS_DB_PORT"; DB_PASSWORD="$NEXUS_DB_PASSWORD"
else
  DB_PASSWORD="$(openssl rand -hex 32)"
  cat > "$ENV_FILE" <<EOF
NEXUS_DB_HOST=$DB_HOST
NEXUS_DB_PORT=$DB_PORT
NEXUS_DB_NAME=$DB_NAME
NEXUS_DB_USER=$DB_USER
NEXUS_DB_PASSWORD=$DB_PASSWORD
NEXUS_DB_SCHEMA=nexus
EOF
  chmod 600 "$ENV_FILE"
fi

log "Creating or updating PostgreSQL role"
sudo -u postgres psql --set=ON_ERROR_STOP=1 --set=db_user="$DB_USER" --set=db_password="$DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:'db_user')\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'db_user', :'db_password')\gexec
SQL

log "Creating database when missing"
sudo -u postgres psql --set=ON_ERROR_STOP=1 --set=db_name="$DB_NAME" --set=db_user="$DB_USER" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname=:'db_name')\gexec
SQL

export PGPASSWORD="$DB_PASSWORD"
for migration in \
  "$MIGRATIONS_DIR/001_nexus_platform_foundation.sql" \
  "$MIGRATIONS_DIR/002_workers_pool_instances_and_playbook_targets.sql" \
  "$MIGRATIONS_DIR/003_home_operations_foundation.sql"
do
  [[ -f "$migration" ]] || die "Missing migration: $migration"
  log "Applying $(basename "$migration")"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$migration"
done

log "Seeding Seymour Lab site"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO nexus.sites(site_id,name,site_type,status,timezone,country,region,metadata)
VALUES('site-seymour-lab','Seymour Lab','home','active','America/Chicago','US','Minnesota','{"source":"database-setup"}'::jsonb)
ON CONFLICT(site_id) DO NOTHING;
SQL

log "Verifying migrations and schema"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<'SQL'
SELECT version,description,applied_at FROM schema_migrations ORDER BY version;
SELECT count(*) AS nexus_table_count FROM pg_tables WHERE schemaname='nexus';
SQL

touch "$PROJECT_ROOT/.gitignore"
grep -qxF 'backend/data/private/' "$PROJECT_ROOT/.gitignore" || echo 'backend/data/private/' >> "$PROJECT_ROOT/.gitignore"

printf '\nNexus PostgreSQL foundation is ready.\nCredentials: %s\n' "$ENV_FILE"
printf 'Next step: import JSON data and switch the repository layer to PostgreSQL.\n'
