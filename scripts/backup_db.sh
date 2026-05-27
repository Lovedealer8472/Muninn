#!/usr/bin/env bash
# Backup Muninn SQLite database with timestamp.
set -euo pipefail

APP_DIR="${1:-$(dirname "$0")/../app}"
DB="${APP_DIR}/pantanakerfi.db"
BACKUP_DIR="${APP_DIR}/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR}/pantanakerfi-${STAMP}.db"

if [[ ! -f "$DB" ]]; then
  echo "Database not found: $DB" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB" ".backup '${DEST}'"
echo "Backup written to ${DEST}"
