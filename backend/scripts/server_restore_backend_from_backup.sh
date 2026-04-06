#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
APP_USER="${APP_USER:-xycardflip}"
APP_GROUP="${APP_GROUP:-xycardflip}"
SHARED_PATH="${APP_ROOT}/shared"
BACKUP_ROOT="${APP_ROOT}/backups"
VERIFY_ONLY=0
ARCHIVE_PATH="${1:-}"

if [ "${ARCHIVE_PATH:-}" = "--verify" ]; then
    VERIFY_ONLY=1
    ARCHIVE_PATH="${2:-}"
fi

if [ -z "${ARCHIVE_PATH}" ]; then
    echo "usage: $0 [--verify] <backup-archive>" >&2
    exit 1
fi

if ! ARCHIVE_REALPATH="$(realpath "${ARCHIVE_PATH}")"; then
    echo "backup archive not found: ${ARCHIVE_PATH}" >&2
    exit 1
fi

BACKUP_ROOT_REALPATH="$(realpath "${BACKUP_ROOT}")"
case "${ARCHIVE_REALPATH}" in
    "${BACKUP_ROOT_REALPATH}"/*) ;;
    *)
        echo "backup archive must live under ${BACKUP_ROOT}" >&2
        exit 1
        ;;
esac

WORK_DIR="$(mktemp -d /tmp/xycardflip-restore-XXXXXX)"
ROLLBACK_DIR="$(mktemp -d /tmp/xycardflip-rollback-XXXXXX)"
RESTORE_STARTED=0

cleanup() {
    rm -rf "${WORK_DIR}" "${ROLLBACK_DIR}"
}

rollback_restore() {
    rollback_rc=$?
    if [ "${RESTORE_STARTED}" != "1" ]; then
        cleanup
        exit "${rollback_rc}"
    fi

    echo "restore failed, attempting rollback..." >&2
    systemctl stop xycardflip-backend.service || true

    if [ -d "${ROLLBACK_DIR}/backend-data" ]; then
        rm -rf "${SHARED_PATH}/backend-data"
        install -d -o "${APP_USER}" -g "${APP_GROUP}" "${SHARED_PATH}/backend-data"
        cp -a "${ROLLBACK_DIR}/backend-data/." "${SHARED_PATH}/backend-data/"
        chown -R "${APP_USER}:${APP_GROUP}" "${SHARED_PATH}/backend-data"
    fi

    if [ -f "${ROLLBACK_DIR}/backend.env" ]; then
        install -m 640 -o root -g "${APP_GROUP}" "${ROLLBACK_DIR}/backend.env" "${SHARED_PATH}/backend.env"
    fi

    systemctl restart xycardflip-backend.service || true
    cleanup
    exit "${rollback_rc}"
}

trap rollback_restore ERR
trap cleanup EXIT

tar -xzf "${ARCHIVE_REALPATH}" -C "${WORK_DIR}"

for required_path in manifest.txt backend.env backend-data/trading.db; do
    if [ ! -e "${WORK_DIR}/${required_path}" ]; then
        echo "backup archive missing ${required_path}" >&2
        exit 1
    fi
done

python3 - "${WORK_DIR}/backend-data/trading.db" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
try:
    result = connection.execute("PRAGMA integrity_check;").fetchone()
finally:
    connection.close()

if not result or result[0] != "ok":
    raise SystemExit(f"sqlite integrity_check failed: {result!r}")
PY

if [ "${VERIFY_ONLY}" = "1" ]; then
    echo "verified=${ARCHIVE_REALPATH}"
    trap - ERR
    exit 0
fi

install -d -o "${APP_USER}" -g "${APP_GROUP}" "${ROLLBACK_DIR}/backend-data"
if [ -d "${SHARED_PATH}/backend-data" ]; then
    cp -a "${SHARED_PATH}/backend-data/." "${ROLLBACK_DIR}/backend-data/"
fi
if [ -f "${SHARED_PATH}/backend.env" ]; then
    cp "${SHARED_PATH}/backend.env" "${ROLLBACK_DIR}/backend.env"
fi

/srv/xycardflip/bin/server_backup_backend_data.sh 7 >/dev/null

RESTORE_STARTED=1

systemctl stop xycardflip-backend.service

rm -rf "${SHARED_PATH}/backend-data"
install -d -o "${APP_USER}" -g "${APP_GROUP}" "${SHARED_PATH}/backend-data"
cp -a "${WORK_DIR}/backend-data/." "${SHARED_PATH}/backend-data/"
chown -R "${APP_USER}:${APP_GROUP}" "${SHARED_PATH}/backend-data"
find "${SHARED_PATH}/backend-data" -type f -exec chmod 660 {} \; 2>/dev/null || true
find "${SHARED_PATH}/backend-data" -type d -exec chmod 750 {} \; 2>/dev/null || true

install -m 640 -o root -g "${APP_GROUP}" "${WORK_DIR}/backend.env" "${SHARED_PATH}/backend.env"

systemctl restart xycardflip-backend.service

for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:18000/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

curl -fsS http://127.0.0.1:18000/health >/dev/null

trap - ERR

echo "restored=${ARCHIVE_REALPATH}"
