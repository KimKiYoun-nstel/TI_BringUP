#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -d "$KERNEL_SRC/.git" ]; then
    echo "[ERROR] Kernel workspace is missing or not a git repo: $KERNEL_SRC" >&2
    exit 1
fi

cd "$KERNEL_SRC"

echo "[INFO] Resetting kernel workspace"
git reset --hard
git clean -fdx

shopt -s nullglob
patches=("$BRINGUP_ROOT"/bsp/linux/patches/*.patch)

if [ ${#patches[@]} -eq 0 ]; then
    echo "[INFO] No Linux patches to apply."
    exit 0
fi

for p in "${patches[@]}"; do
    echo "[INFO] Applying Linux patch: $p"
    git am "$p"
done

echo "[INFO] Linux patches applied."
