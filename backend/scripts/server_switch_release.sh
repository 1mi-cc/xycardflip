#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
RELEASE_ID="${1:-}"

if [ -z "${RELEASE_ID}" ]; then
    echo "usage: $0 <release-id>" >&2
    exit 1
fi

TARGET="${APP_ROOT}/releases/${RELEASE_ID}"
CURRENT="${APP_ROOT}/current"
PREVIOUS_TARGET="$(readlink -f "${CURRENT}" 2>/dev/null || true)"
ROLLED_FORWARD=0

if [ ! -d "${TARGET}" ]; then
    echo "release not found: ${TARGET}" >&2
    exit 1
fi

rollback_release() {
    rollback_rc=$?
    if [ "${ROLLED_FORWARD}" != "1" ]; then
        exit "${rollback_rc}"
    fi
    echo "release switch failed, attempting rollback..." >&2
    if [ -n "${PREVIOUS_TARGET}" ] && [ -d "${PREVIOUS_TARGET}" ]; then
        ln -sfn "${PREVIOUS_TARGET}" "${CURRENT}" || true
        systemctl restart xycardflip-backend.service || true
        nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    fi
    exit "${rollback_rc}"
}

trap rollback_release ERR

ln -sfn "${TARGET}" "${CURRENT}"
ROLLED_FORWARD=1
systemctl restart xycardflip-backend.service
curl -fsS http://127.0.0.1:18000/health >/dev/null
systemctl reload nginx
curl -fsS http://127.0.0.1:8000/health >/dev/null

trap - ERR

echo "current=${TARGET}"
