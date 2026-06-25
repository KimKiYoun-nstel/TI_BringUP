#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PREP_HELPER="$BRINGUP_ROOT/tools/prepare/apply-mcu-plus-sk-am64b-sbl-ospi-linux-local-fullchain.sh"
SBL_EXAMPLE="examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang"
FLASH_CFG="$BRINGUP_ROOT/bsp/mcu-plus/configs/sbl_ospi_linux_sk-am64b_local-fullchain.cfg"
SBL_SRC="$BRINGUP_ROOT/workspace/mcu_plus_sdk_am64x_12_00_00_27/examples/drivers/boot/sbl_ospi_linux/am64x-evm/r5fss0-0_nortos/ti-arm-clang/sbl_ospi_linux.release.hs_fs.tiimage"
R5F_SRC="$BRINGUP_ROOT/out/sk-am64b-r5f-early-boot/images/r5f-early-heartbeat.mcelf.hs_fs"
UBOOT_SRC="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-build-local-fullchain/u-boot.img"
LINUX_SRC="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-build-local-fullchain/linux.mcelf.hs_fs"
LINUX_MANIFEST_SRC="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-build-local-fullchain/build-manifest.txt"
OUT_SET_DIR="$BRINGUP_ROOT/out/sk-am64b-sbl-ospi-linux-local-fullchain"
OUT_MANIFEST="$OUT_SET_DIR/build-manifest.txt"

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

stage_outputs() {
    mkdir -p "$OUT_SET_DIR"
    cp "$SBL_SRC" "$OUT_SET_DIR/sbl_ospi_linux.release.hs_fs.tiimage"
    cp "$R5F_SRC" "$OUT_SET_DIR/r5f-early-heartbeat.mcelf.hs_fs"
    cp "$UBOOT_SRC" "$OUT_SET_DIR/u-boot.img"
    cp "$LINUX_SRC" "$OUT_SET_DIR/linux.mcelf.hs_fs"
    cp "$LINUX_SRC" "$OUT_SET_DIR/0x800000_linux.mcelf.hs_fs"
    if [ -f "$LINUX_MANIFEST_SRC" ]; then
        cp "$LINUX_MANIFEST_SRC" "$OUT_SET_DIR/linux-appimage-build-manifest.txt"
    fi

    {
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'Workspace prep helper: %s\n' "$PREP_HELPER"
        printf 'SBL example source: %s\n' "$SBL_EXAMPLE"
        printf 'Flash cfg: %s\n' "$FLASH_CFG"
        printf '\n[source artifacts]\n'
        printf 'SBL source   : %s\n' "$SBL_SRC"
        printf 'R5F source   : %s\n' "$R5F_SRC"
        printf 'U-Boot source: %s\n' "$UBOOT_SRC"
        printf 'Linux source : %s\n' "$LINUX_SRC"
        printf '\n[staged artifacts]\n'
        printf 'SBL   : %s\n' "$OUT_SET_DIR/sbl_ospi_linux.release.hs_fs.tiimage"
        printf 'R5F   : %s\n' "$OUT_SET_DIR/r5f-early-heartbeat.mcelf.hs_fs"
        printf 'U-Boot: %s\n' "$OUT_SET_DIR/u-boot.img"
        printf 'Linux : %s\n' "$OUT_SET_DIR/linux.mcelf.hs_fs"
        printf '\n[sha256]\n'
        sha256sum \
            "$OUT_SET_DIR/sbl_ospi_linux.release.hs_fs.tiimage" \
            "$OUT_SET_DIR/r5f-early-heartbeat.mcelf.hs_fs" \
            "$OUT_SET_DIR/u-boot.img" \
            "$OUT_SET_DIR/linux.mcelf.hs_fs"
    } > "$OUT_MANIFEST"
}

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh --print
  ./tools/build/build-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build

Rebuild the current canonical SK-AM64B `SBL OSPI Linux` local-fullchain set:
- LPDDR4-aligned `sbl_ospi_linux` SBL
- early-boot R5F app and signed multicore appimage
- local-fullchain linux appimage
EOF
}

MODE="${1:---print}"

case "$MODE" in
    --print)
        printf 'Workspace prep helper : %s\n' "$PREP_HELPER"
        printf 'SBL example source    : %s\n' "$SBL_EXAMPLE"
        printf 'Flash cfg             : %s\n' "$FLASH_CFG"
        printf 'Build steps           : prepare -> SBL -> R5F ELF -> R5F appimage -> linux appimage -> stage final set\n'
        printf 'Workspace-built src   :\n'
        printf '  SBL   : %s\n' "$SBL_SRC"
        printf '  R5F   : %s\n' "$R5F_SRC"
        printf '  U-Boot: %s\n' "$UBOOT_SRC"
        printf '  Linux : %s\n' "$LINUX_SRC"
        printf 'Repo-managed out set  : %s\n' "$OUT_SET_DIR"
        printf 'Staged final outputs  :\n'
        printf '  SBL   : %s\n' "$OUT_SET_DIR/sbl_ospi_linux.release.hs_fs.tiimage"
        printf '  R5F   : %s\n' "$OUT_SET_DIR/r5f-early-heartbeat.mcelf.hs_fs"
        printf '  U-Boot: %s\n' "$OUT_SET_DIR/u-boot.img"
        printf '  Linux : %s\n' "$OUT_SET_DIR/linux.mcelf.hs_fs"
        ;;
    --build)
        "$PREP_HELPER" --apply
        "$BRINGUP_ROOT/tools/build/build-mcu-plus-example.sh" make "$SBL_EXAMPLE" release
        "$BRINGUP_ROOT/tools/build/build-r5f-early-boot-app.sh" r5f Release
        "$BRINGUP_ROOT/tools/build/gen-r5f-multicore-appimage.sh" --execute
        "$BRINGUP_ROOT/tools/build/gen-linux-appimage-for-sbl.sh" --execute --profile local-fullchain
        require_file "$SBL_SRC"
        require_file "$R5F_SRC"
        require_file "$UBOOT_SRC"
        require_file "$LINUX_SRC"
        stage_outputs
        printf '[OK] staged final set: %s\n' "$OUT_SET_DIR"
        cat "$OUT_MANIFEST"
        ;;
    *)
        usage
        exit 1
        ;;
esac
