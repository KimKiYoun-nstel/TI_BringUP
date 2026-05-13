#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -d "$UBOOT_SRC/.git" ]; then
    echo "[ERROR] U-Boot workspace is missing or not a git repo: $UBOOT_SRC" >&2
    exit 1
fi

cd "$UBOOT_SRC"

echo "[INFO] Resetting U-Boot workspace"
git reset --hard
git clean -fdx

shopt -s nullglob
patches=("$BRINGUP_ROOT"/bsp/u-boot/patches/*.patch)

if [ ${#patches[@]} -eq 0 ]; then
    echo "[INFO] No U-Boot patches to apply."
    exit 0
fi

for p in "${patches[@]}"; do
    echo "[INFO] Applying U-Boot patch: $p"
    git am "$p"
done

echo "[INFO] U-Boot patches applied."
