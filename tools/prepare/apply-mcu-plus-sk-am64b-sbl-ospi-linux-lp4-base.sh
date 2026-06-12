#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"

ASSET_PATH="$BRINGUP_ROOT/bsp/mcu-plus/syscfg/board_ddrReginit_sk_am64b_lpddr4.h"
PATCH_PATH="$BRINGUP_ROOT/bsp/mcu-plus/patches/0002-am64x-sbl-ospi-linux-keep-lp4-dual-boot-workspace-base.patch"

usage() {
    cat <<'EOF'
Usage:
  ./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh --check
  ./tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-lp4-base.sh --apply

Apply or verify the current clean SK-AM64B SBL OSPI Linux LPDDR4 workspace base.

This helper does two things:
1. copy the repo-managed LPDDR4 board_ddrReginit asset into the MCU+ workspace
2. apply the clean sbl_ospi_linux syscfg delta kept in patch 0002
EOF
}

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

require_dir() {
    local path="$1"
    if [ ! -d "$path" ]; then
        echo "[ERROR] Missing directory: $path" >&2
        exit 1
    fi
}

sha256_of() {
    sha256sum "$1" | cut -d' ' -f1
}

MODE="${1:---check}"

require_file "$MCU_ENV_FILE"
require_file "$ASSET_PATH"
require_file "$PATCH_PATH"

# shellcheck disable=SC1090
source "$MCU_ENV_FILE"

WORKSPACE_ROOT="$MCU_PLUS_SDK_PATH"
DDR_DST="$WORKSPACE_ROOT/source/drivers/ddr/v0/soc/am64x_am243x/board_ddrReginit.h"
SYSCFG_DST="$WORKSPACE_ROOT/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/example.syscfg"

require_dir "$WORKSPACE_ROOT"
require_file "$DDR_DST"
require_file "$SYSCFG_DST"

verify_state() {
    local asset_hash dst_hash

    asset_hash="$(sha256_of "$ASSET_PATH")"
    dst_hash="$(sha256_of "$DDR_DST")"

    echo "[INFO] LPDDR4 asset sha256     : $asset_hash"
    echo "[INFO] Workspace DDR sha256   : $dst_hash"

    if [ "$asset_hash" != "$dst_hash" ]; then
        echo "[ERROR] Workspace DDR reginit does not match repo-managed LPDDR4 asset" >&2
        return 1
    fi

    if ! grep -Fq 'mpu_armv75.attributes  = "NonCached";' "$SYSCFG_DST"; then
        echo "[ERROR] Missing NonCached appimage MPU delta in $SYSCFG_DST" >&2
        return 1
    fi

    if ! grep -Fq 'mpu_armv75.allowExecute = false;' "$SYSCFG_DST"; then
        echo "[ERROR] Missing no-exec appimage MPU delta in $SYSCFG_DST" >&2
        return 1
    fi

    echo "[OK] Workspace matches the current clean LP4 base"
}

apply_state() {
    cp "$ASSET_PATH" "$DDR_DST"
    echo "[OK] Copied LPDDR4 reginit asset to workspace"

    if grep -Fq 'mpu_armv75.attributes  = "NonCached";' "$SYSCFG_DST" && \
       grep -Fq 'mpu_armv75.allowExecute = false;' "$SYSCFG_DST"; then
        echo "[OK] Syscfg delta already present"
    else
        patch --forward -d "$WORKSPACE_ROOT" -p1 < "$PATCH_PATH"
        echo "[OK] Applied clean sbl_ospi_linux syscfg patch"
    fi

    verify_state
}

case "$MODE" in
    --check)
        verify_state
        ;;
    --apply)
        apply_state
        ;;
    *)
        usage
        exit 1
        ;;
esac
