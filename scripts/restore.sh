#!/usr/bin/env bash
# ==============================================================================
# Callwise Automated Database Restore Script (POSIX)
# Restores a compressed pg_dump archive (.sql.gz) into Callwise database
# ==============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <path_to_backup_file.sql.gz>"
    echo "Example: $0 backups/callwise_backup_20261107_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' does not exist." >&2
    exit 1
fi

echo "=== Callwise Database Restore ==="
echo "Restoring from: ${BACKUP_FILE}"

if command -v callwise &> /dev/null; then
    callwise db restore "${BACKUP_FILE}"
elif command -v uv &> /dev/null; then
    uv run python -m callwise.cli db restore "${BACKUP_FILE}"
elif command -v psql &> /dev/null; then
    DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5433/callwise}"
    CLEAN_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
    CLEAN_URL="${CLEAN_URL/postgresql+psycopg:\/\//postgresql:\/\/}"

    gunzip -c "${BACKUP_FILE}" | psql "${CLEAN_URL}" -v ON_ERROR_STOP=0
    echo "[OK] Restore completed successfully."
else
    echo "ERROR: Neither callwise CLI nor psql was found on PATH." >&2
    exit 1
fi

echo "=== Restore Complete ==="

