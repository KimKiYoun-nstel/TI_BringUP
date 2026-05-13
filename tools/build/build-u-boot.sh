#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -d "$UBOOT_SRC" ]; then
    echo "[ERROR] UBOOT_SRC not found: $UBOOT_SRC" >&2
    exit 1
fi

cd "$UBOOT_SRC"
mkdir -p "$BRINGUP_ROOT/out/u-boot"

cat <<'MSG'
[TODO] U-Boot build script skeleton only.
Fill in exact commands from the already-verified manual build procedure.
Expected artifacts:
  - tiboot3.bin
  - tispl.bin
  - u-boot.img
MSG
