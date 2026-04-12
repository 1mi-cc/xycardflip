#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
APP_USER="${APP_USER:-xycardflip}"
APP_GROUP="${APP_GROUP:-xycardflip}"
BACKUP_ROOT="${APP_ROOT}/backups"
CURRENT_BACKEND="${APP_ROOT}/current/backend"
CURRENT_FRONTEND_DIST="${APP_ROOT}/current/dist"
PORT="${PORT:-18100}"
STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC:-45}"
ARCHIVE_PATH="${1:-}"

if [ -z "${ARCHIVE_PATH}" ]; then
    ARCHIVE_PATH="$(find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'xycardflip-backup-*.tar.gz' | sort -r | head -n 1)"
fi

if [ -z "${ARCHIVE_PATH}" ]; then
    echo "no backup archive found under ${BACKUP_ROOT}" >&2
    exit 1
fi

ARCHIVE_REALPATH="$(realpath "${ARCHIVE_PATH}")"
WORK_DIR="$(mktemp -d /tmp/xycardflip-rehearsal-XXXXXX)"
chown root:"${APP_GROUP}" "${WORK_DIR}"
chmod 750 "${WORK_DIR}"
EXTRACT_DIR="${WORK_DIR}/extract"
RUNTIME_DIR="${WORK_DIR}/runtime"
RUNTIME_DATA_DIR="${RUNTIME_DIR}/backend-data"
RUNTIME_ENV_PATH="${RUNTIME_DIR}/backend.env"
HEALTH_PAYLOAD_PATH="${WORK_DIR}/health.json"
LOG_PATH="${RUNTIME_DIR}/uvicorn.log"
PID_PATH="${RUNTIME_DIR}/uvicorn.pid"
RUNNER_PID=""

fail_with_log() {
    echo "$1" >&2
    if [ -f "${LOG_PATH}" ]; then
        echo "--- rehearsal log ---" >&2
        tail -n 40 "${LOG_PATH}" >&2 || true
    fi
    exit 1
}

cleanup() {
    if [ -f "${PID_PATH}" ]; then
        app_pid="$(cat "${PID_PATH}" 2>/dev/null || true)"
        if [ -n "${app_pid}" ]; then
            kill "${app_pid}" 2>/dev/null || true
        fi
    fi
    if [ -n "${RUNNER_PID}" ]; then
        wait "${RUNNER_PID}" 2>/dev/null || true
    fi
    rm -rf "${WORK_DIR}"
}

trap cleanup EXIT

/srv/xycardflip/bin/server_restore_backend_from_backup.sh --verify "${ARCHIVE_REALPATH}" >/dev/null

install -d "${EXTRACT_DIR}"
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 750 "${RUNTIME_DIR}" "${RUNTIME_DATA_DIR}"
touch "${LOG_PATH}" "${PID_PATH}"
chown "${APP_USER}:${APP_GROUP}" "${LOG_PATH}" "${PID_PATH}"

tar -xzf "${ARCHIVE_REALPATH}" -C "${EXTRACT_DIR}"
cp -a "${EXTRACT_DIR}/backend-data/." "${RUNTIME_DATA_DIR}/"
chown -R "${APP_USER}:${APP_GROUP}" "${RUNTIME_DATA_DIR}"
find "${RUNTIME_DATA_DIR}" -type f -exec chmod 660 {} \; 2>/dev/null || true
find "${RUNTIME_DATA_DIR}" -type d -exec chmod 750 {} \; 2>/dev/null || true
install -m 640 -o root -g "${APP_GROUP}" "${EXTRACT_DIR}/backend.env" "${RUNTIME_ENV_PATH}"

runuser -u "${APP_USER}" -- env \
    DOTENV_PATH="${RUNTIME_ENV_PATH}" \
    SQLITE_PATH="${RUNTIME_DATA_DIR}/trading.db" \
    FRONTEND_DIST="${CURRENT_FRONTEND_DIST}" \
    APP_ENV="restore_rehearsal" \
    AUTO_START_MONITOR="false" \
    AUTO_START_AUTOTRADE="false" \
    AUTO_START_EXECUTION_RETRY="false" \
    AUTO_START_SUPABASE_SYNC="false" \
    AUTO_APPROVE_ENABLED="false" \
    EXECUTION_LIVE_ENABLED="false" \
    ALERT_EMAIL_ENABLED="false" \
    ALERT_SLACK_ENABLED="false" \
    ALERT_TELEGRAM_ENABLED="false" \
    ALERT_WEBHOOK_ENABLED="false" \
    AUTOTRADE_ALERT_EMAIL_AUTO_ENABLED="false" \
    AUTOTRADE_ALERT_SLACK_AUTO_ENABLED="false" \
    AUTOTRADE_ALERT_TELEGRAM_AUTO_ENABLED="false" \
    AUTOTRADE_ALERT_WEBHOOK_AUTO_ENABLED="false" \
    bash -lc "cd '${CURRENT_BACKEND}' && /srv/xycardflip/shared/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port '${PORT}' >'${LOG_PATH}' 2>&1 & echo \$! >'${PID_PATH}'; wait \$(cat '${PID_PATH}')" &
RUNNER_PID=$!

for _ in $(seq 1 "${STARTUP_TIMEOUT_SEC}"); do
    if curl -fsS "http://127.0.0.1:${PORT}/health" > "${HEALTH_PAYLOAD_PATH}"; then
        break
    fi
    if ! kill -0 "${RUNNER_PID}" 2>/dev/null; then
        fail_with_log "restore rehearsal app exited before becoming healthy"
    fi
    sleep 1
done

if [ ! -s "${HEALTH_PAYLOAD_PATH}" ]; then
    fail_with_log "restore rehearsal health endpoint did not become ready in time"
fi

python3 - "${HEALTH_PAYLOAD_PATH}" "${RUNTIME_DATA_DIR}/trading.db" <<'PY'
import json
import pathlib
import sys

health_path = pathlib.Path(sys.argv[1])
expected_db = pathlib.Path(sys.argv[2]).resolve()

payload = json.loads(health_path.read_text(encoding="utf-8"))
if payload.get("status") != "ok":
    raise SystemExit(f"unexpected health status: {payload.get('status')!r}")

database = payload.get("database") or {}
if not bool(database.get("available")):
    raise SystemExit("database was not available during restore rehearsal")

actual_db = pathlib.Path(str(database.get("sqlite_path") or "")).resolve()
if actual_db != expected_db:
    raise SystemExit(f"restore rehearsal used unexpected sqlite path: {actual_db} != {expected_db}")

auto_start = payload.get("auto_start") or {}
if any(bool(value) for value in auto_start.values()):
    raise SystemExit(f"restore rehearsal booted with unsafe auto_start flags: {auto_start!r}")
PY

curl -fsS "http://127.0.0.1:${PORT}/health/ready" >/dev/null || true

echo "rehearsal_ok=${ARCHIVE_REALPATH}"
echo "rehearsal_port=${PORT}"
