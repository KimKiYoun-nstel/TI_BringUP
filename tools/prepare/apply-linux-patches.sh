#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

SERIES_FILE="$BRINGUP_ROOT/bsp/linux/patches/series"

if [ ! -d "$KERNEL_SRC/.git" ]; then
    echo "[ERROR] Kernel workspace is missing or not a git repo: $KERNEL_SRC" >&2
    exit 1
fi

cd "$KERNEL_SRC"

echo "[INFO] Resetting kernel workspace"
git reset --hard
git clean -fdx

if [ ! -f "$SERIES_FILE" ]; then
    echo "[INFO] No Linux series file found: $SERIES_FILE"
    exit 0
fi

while IFS= read -r entry; do
    case "$entry" in
        ""|\#*)
            continue
            ;;
    esac

    p="$BRINGUP_ROOT/bsp/linux/patches/$entry"
    if [ ! -f "$p" ]; then
        echo "[ERROR] Listed Linux patch missing from series: $p" >&2
        exit 1
    fi

    echo "[INFO] Applying Linux patch: $p"
    git am "$p"
done < "$SERIES_FILE"

echo "[INFO] Linux patches applied."
