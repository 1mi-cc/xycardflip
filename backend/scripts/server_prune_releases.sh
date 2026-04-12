#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/srv/xycardflip}"
KEEP_COUNT="${1:-5}"
MAX_TOTAL_MB="${2:-0}"

if ! [[ "${KEEP_COUNT}" =~ ^[0-9]+$ ]]; then
    echo "keep count must be an integer" >&2
    exit 1
fi

if ! [[ "${MAX_TOTAL_MB}" =~ ^[0-9]+$ ]]; then
    echo "max total MB must be an integer" >&2
    exit 1
fi

KEEP_COUNT=$((KEEP_COUNT))
if [ "${KEEP_COUNT}" -lt 1 ]; then
    echo "keep count must be >= 1" >&2
    exit 1
fi

MAX_TOTAL_MB=$((MAX_TOTAL_MB))
if [ "${MAX_TOTAL_MB}" -lt 0 ]; then
    echo "max total MB must be >= 0" >&2
    exit 1
fi

release_size_mb() {
    du -sm "$1" | awk '{print $1}'
}

CURRENT_TARGET="$(readlink -f "${APP_ROOT}/current" 2>/dev/null || true)"
mapfile -t RELEASE_DIRS < <(find "${APP_ROOT}/releases" -mindepth 1 -maxdepth 1 -type d | sort -r)
declare -a KEPT_RELEASES=()

index=0
for release_dir in "${RELEASE_DIRS[@]}"; do
    index=$((index + 1))
    if [ "${release_dir}" = "${CURRENT_TARGET}" ]; then
        echo "keep current ${release_dir}"
        KEPT_RELEASES+=("${release_dir}")
        continue
    fi
    if [ "${index}" -le "${KEEP_COUNT}" ]; then
        echo "keep ${release_dir}"
        KEPT_RELEASES+=("${release_dir}")
        continue
    fi
    echo "prune ${release_dir}"
    rm -rf "${release_dir}"
done

if [ "${MAX_TOTAL_MB}" -eq 0 ]; then
    exit 0
fi

total_mb=0
for release_dir in "${KEPT_RELEASES[@]}"; do
    total_mb=$((total_mb + $(release_size_mb "${release_dir}")))
done

if [ "${total_mb}" -le "${MAX_TOTAL_MB}" ]; then
    echo "release budget ok ${total_mb}MB/${MAX_TOTAL_MB}MB"
    exit 0
fi

mapfile -t BUDGET_PRUNE_CANDIDATES < <(printf '%s\n' "${KEPT_RELEASES[@]}" | sort)
for release_dir in "${BUDGET_PRUNE_CANDIDATES[@]}"; do
    if [ "${release_dir}" = "${CURRENT_TARGET}" ]; then
        continue
    fi
    if [ "${total_mb}" -le "${MAX_TOTAL_MB}" ]; then
        break
    fi
    release_mb="$(release_size_mb "${release_dir}")"
    echo "budget prune ${release_dir} (${release_mb}MB)"
    rm -rf "${release_dir}"
    total_mb=$((total_mb - release_mb))
done

echo "release budget final ${total_mb}MB/${MAX_TOTAL_MB}MB"
