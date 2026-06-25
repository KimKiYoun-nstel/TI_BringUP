#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
LP4_HELPER="$BRINGUP_ROOT/tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh"
PATCH_PATH="$BRINGUP_ROOT/bsp/mcu-plus/patches/0003-am64x-linuxappimagegen-pyelftools-compat.patch"

usage() {
    cat <<'EOF'
Usage:
  ./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh --check
  ./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh --apply

Prepare or verify the reproducible SK-AM64B `sbl_ospi_linux` local-fullchain workspace base.

This helper does two things:
1. apply/verify the existing LPDDR4 clean workspace base
2. apply/verify the linuxAppimageGen pyelftools compatibility patch
EOF
}

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

MODE="${1:---check}"

require_file "$MCU_ENV_FILE"
require_file "$LP4_HELPER"
require_file "$PATCH_PATH"

# shellcheck disable=SC1090
source "$MCU_ENV_FILE"

TARGET_FILE="$MCU_PLUS_SDK_PATH/tools/boot/multicore-elf/modules_am64/multicoreelf.py"
require_file "$TARGET_FILE"

verify_pyelftools_patch() {
    if ! grep -Fq "for segment in elf_o.iter_segments():" "$TARGET_FILE"; then
        echo "[ERROR] Missing pyelftools compatibility loop in $TARGET_FILE" >&2
        return 1
    fi
    if ! grep -Fq "segment.header['p_type'] != 'PT_LOAD'" "$TARGET_FILE"; then
        echo "[ERROR] Missing PT_LOAD filter in $TARGET_FILE" >&2
        return 1
    fi
    echo "[OK] linuxAppimageGen pyelftools compatibility patch is present"
}

apply_pyelftools_patch() {
    if verify_pyelftools_patch >/dev/null 2>&1; then
        echo "[OK] linuxAppimageGen pyelftools compatibility patch already present"
        return 0
    fi
    patch --forward -d "$MCU_PLUS_SDK_PATH" -p1 < "$PATCH_PATH"
    echo "[OK] Applied linuxAppimageGen pyelftools compatibility patch"
}

case "$MODE" in
    --check)
        "$LP4_HELPER" --check
        verify_pyelftools_patch
        ;;
    --apply)
        "$LP4_HELPER" --apply
        apply_pyelftools_patch
        verify_pyelftools_patch
        ;;
    *)
        usage
        exit 1
        ;;
esac
