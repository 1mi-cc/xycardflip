#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
APP_GROUP="${APP_GROUP:-xycardflip}"
SHARED_PATH="${APP_ROOT}/shared"
BACKUP_ROOT="${APP_ROOT}/backups"
RETENTION_COUNT="${1:-7}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_PATH="${BACKUP_ROOT}/xycardflip-backup-${TIMESTAMP}.tar.gz"
TEMP_DIR="$(mktemp -d /tmp/xycardflip-backup-XXXXXX)"

cleanup() {
    rm -rf "${TEMP_DIR}"
}

trap cleanup EXIT

if ! [[ "${RETENTION_COUNT}" =~ ^[0-9]+$ ]]; then
    echo "retention count must be an integer" >&2
    exit 1
fi

RETENTION_COUNT=$((RETENTION_COUNT))
if [ "${RETENTION_COUNT}" -lt 1 ]; then
    echo "retention count must be >= 1" >&2
    exit 1
fi

install -d -o root -g "${APP_GROUP}" -m 750 "${BACKUP_ROOT}"
install -d -m 750 "${TEMP_DIR}/backend-data"

if [ -d "${SHARED_PATH}/backend-data" ]; then
    tar \
        --exclude="trading.db" \
        -C "${SHARED_PATH}/backend-data" \
        -cf - . | tar -C "${TEMP_DIR}/backend-data" -xf -
fi

DB_SOURCE="${SHARED_PATH}/backend-data/trading.db"
DB_BACKUP="${TEMP_DIR}/backend-data/trading.db"

if [ -f "${DB_SOURCE}" ]; then
    python3 - "${DB_SOURCE}" "${DB_BACKUP}" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1], sys.argv[2]
source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
backup = sqlite3.connect(backup_path)
with backup:
    source.backup(backup)
backup.close()
source.close()
PY
fi

if [ -f "${SHARED_PATH}/backend.env" ]; then
    cp "${SHARED_PATH}/backend.env" "${TEMP_DIR}/backend.env"
    chmod 600 "${TEMP_DIR}/backend.env"
fi

if [ -f "${APP_ROOT}/current/.release-meta" ]; then
    cp "${APP_ROOT}/current/.release-meta" "${TEMP_DIR}/release-meta"
fi

cat > "${TEMP_DIR}/manifest.txt" <<EOF
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
app_root=${APP_ROOT}
retention_count=${RETENTION_COUNT}
current_release=$(grep '^release_id=' "${APP_ROOT}/current/.release-meta" 2>/dev/null | cut -d= -f2- || echo unknown)
EOF

tar -czf "${ARCHIVE_PATH}" -C "${TEMP_DIR}" .
chown root:"${APP_GROUP}" "${ARCHIVE_PATH}"
chmod 640 "${ARCHIVE_PATH}"

mapfile -t BACKUP_ARCHIVES < <(find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type f -name 'xycardflip-backup-*.tar.gz' | sort -r)

index=0
for archive in "${BACKUP_ARCHIVES[@]}"; do
    index=$((index + 1))
    if [ "${index}" -le "${RETENTION_COUNT}" ]; then
        echo "keep ${archive}"
        continue
    fi
    echo "prune ${archive}"
    rm -f "${archive}"
done

echo "backup=${ARCHIVE_PATH}"
