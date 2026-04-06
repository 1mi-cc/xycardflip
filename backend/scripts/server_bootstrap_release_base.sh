#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-xycardflip}"
APP_GROUP="${APP_GROUP:-xycardflip}"
APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
SOURCE_ROOT="${SOURCE_ROOT:-/opt/xycardflip-main}"
RELEASE_ID="${RELEASE_ID:-$(date -u +%Y%m%d%H%M%S)}"
RELEASE_PATH="${APP_ROOT}/releases/${RELEASE_ID}"
SHARED_PATH="${APP_ROOT}/shared"
CURRENT_PATH="${APP_ROOT}/current"
SOURCE_LABEL="${SOURCE_LABEL:-unknown}"
SOURCE_BRANCH="${SOURCE_BRANCH:-unknown}"
SOURCE_COMMIT="${SOURCE_COMMIT:-unknown}"
SOURCE_DIRTY="${SOURCE_DIRTY:-unknown}"
PREVIOUS_TARGET="$(readlink -f "${CURRENT_PATH}" 2>/dev/null || true)"
ROLLED_FORWARD=0

rollback_release() {
    rollback_rc=$?
    if [ "${ROLLED_FORWARD}" != "1" ]; then
        exit "${rollback_rc}"
    fi
    echo "release bootstrap failed, attempting rollback..." >&2
    if [ -n "${PREVIOUS_TARGET}" ] && [ -d "${PREVIOUS_TARGET}" ]; then
        ln -sfn "${PREVIOUS_TARGET}" "${CURRENT_PATH}" || true
        systemctl restart xycardflip-backend.service || true
        nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    fi
    exit "${rollback_rc}"
}

trap rollback_release ERR

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${APP_USER}"
fi

install -d -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/releases"
install -d -o "${APP_USER}" -g "${APP_GROUP}" "${SHARED_PATH}/backend-data"
install -d -o "${APP_USER}" -g "${APP_GROUP}" "${SHARED_PATH}/logs"
install -d -o root -g "${APP_GROUP}" -m 750 "${APP_ROOT}/backups"

if [ ! -f "${SHARED_PATH}/backend.env" ] && [ -f "${SOURCE_ROOT}/backend/.env" ]; then
    install -m 640 -o root -g "${APP_GROUP}" "${SOURCE_ROOT}/backend/.env" "${SHARED_PATH}/backend.env"
fi

if [ -d "${SOURCE_ROOT}/backend/data" ] && [ -z "$(find "${SHARED_PATH}/backend-data" -mindepth 1 -print -quit 2>/dev/null)" ]; then
    cp -a "${SOURCE_ROOT}/backend/data/." "${SHARED_PATH}/backend-data/"
    chown -R "${APP_USER}:${APP_GROUP}" "${SHARED_PATH}/backend-data"
fi

chmod 640 "${SHARED_PATH}/backend.env" 2>/dev/null || true
find "${SHARED_PATH}/backend-data" -type f -exec chmod 660 {} \; 2>/dev/null || true
find "${SHARED_PATH}/backend-data" -type d -exec chmod 750 {} \; 2>/dev/null || true

rm -rf "${RELEASE_PATH}"
if command -v rsync >/dev/null 2>&1; then
    rsync -a \
        --exclude ".git" \
        --exclude ".codex" \
        --exclude ".github" \
        --exclude ".vscode" \
        --exclude "node_modules" \
        --exclude "release" \
        --exclude "third_party" \
        --exclude "xxzl" \
        --exclude "backend/.venv" \
        --exclude "backend/.venv_pack" \
        --exclude "backend/build" \
        --exclude "backend/dist" \
        --exclude "backend/data" \
        "${SOURCE_ROOT}/" "${RELEASE_PATH}/"
else
    mkdir -p "${RELEASE_PATH}"
    tar \
        --exclude=".git" \
        --exclude=".codex" \
        --exclude=".github" \
        --exclude=".vscode" \
        --exclude="node_modules" \
        --exclude="release" \
        --exclude="third_party" \
        --exclude="xxzl" \
        --exclude="backend/.venv" \
        --exclude="backend/.venv_pack" \
        --exclude="backend/build" \
        --exclude="backend/dist" \
        --exclude="backend/data" \
        -C "${SOURCE_ROOT}" -cf - . | tar -C "${RELEASE_PATH}" -xf -
fi

rm -rf "${RELEASE_PATH}/backend/data"
ln -sfn "${SHARED_PATH}/backend-data" "${RELEASE_PATH}/backend/data"
ln -sfn "${SHARED_PATH}/backend.env" "${RELEASE_PATH}/backend/.env"

python3 -m venv "${SHARED_PATH}/.venv"
"${SHARED_PATH}/.venv/bin/pip" install --upgrade pip
"${SHARED_PATH}/.venv/bin/pip" install -r "${RELEASE_PATH}/backend/requirements.txt"

install -d -o "${APP_USER}" -g "${APP_GROUP}" "${APP_ROOT}/bin"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_ROOT}/releases"
chown -R "${APP_USER}:${APP_GROUP}" "${SHARED_PATH}/backend-data" "${SHARED_PATH}/logs" "${APP_ROOT}/bin"
chown root:"${APP_GROUP}" "${SHARED_PATH}/backend.env" 2>/dev/null || true
chown root:"${APP_GROUP}" "${APP_ROOT}/backups" 2>/dev/null || true

ln -sfn "${RELEASE_PATH}" "${CURRENT_PATH}"
ROLLED_FORWARD=1

cat > "${RELEASE_PATH}/.release-meta" <<EOF
deployed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_root=${SOURCE_LABEL}
source_artifact_root=${SOURCE_ROOT}
source_branch=${SOURCE_BRANCH}
source_commit=${SOURCE_COMMIT}
source_dirty=${SOURCE_DIRTY}
release_id=${RELEASE_ID}
EOF

systemctl daemon-reload
systemctl enable xycardflip-backend.service
systemctl restart xycardflip-backend.service

nginx -t
systemctl reload nginx

chown "${APP_USER}:${APP_GROUP}" "${RELEASE_PATH}/.release-meta"

for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:18000/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

curl -fsS http://127.0.0.1:18000/health >/dev/null
curl -fsS http://127.0.0.1:8000/health >/dev/null

trap - ERR

echo "release=${RELEASE_ID}"
echo "current=${CURRENT_PATH}"
