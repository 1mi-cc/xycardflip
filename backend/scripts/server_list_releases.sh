#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"

for meta in "${APP_ROOT}"/releases/*/.release-meta; do
    [ -f "${meta}" ] || continue
    release_dir="$(dirname "${meta}")"
    release_id="$(basename "${release_dir}")"
    echo "== ${release_id} =="
    cat "${meta}"
    if [ "$(readlink -f "${APP_ROOT}/current")" = "$(readlink -f "${release_dir}")" ]; then
        echo "current=true"
    else
        echo "current=false"
    fi
    echo
done
