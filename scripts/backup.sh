#!/usr/bin/env bash
# ==============================================================================
# Callwise Automated Database Backup Script (POSIX)
# Creates a compressed, timestamped pg_dump archive in backups/
# ==============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/callwise_backup_${TIMESTAMP}.sql.gz"

echo "=== Callwise Database Backup ==="
echo "Destination: ${BACKUP_FILE}"

# If python with callwise cli is available, run CLI backup command
if command -v callwise &> /dev/null; then
    callwise db backup --output-dir "${BACKUP_DIR}"
elif command -v uv &> /dev/null; then
    uv run python -m callwise.cli db backup --output-dir "${BACKUP_DIR}"
elif command -v pg_dump &> /dev/null; then
    DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5433/callwise}"
    # Strip asyncpg/psycopg prefixes if present
    CLEAN_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
    CLEAN_URL="${CLEAN_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
    
    pg_dump "${CLEAN_URL}" --clean --if-exists --no-owner --no-privileges | gzip > "${BACKUP_FILE}"
    echo "[OK] Backup created at: ${BACKUP_FILE}"
else
    echo "ERROR: Neither callwise CLI nor pg_dump was found on PATH." >&2
    exit 1
fi

echo "=== Backup Complete ==="

