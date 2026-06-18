#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

MODE="all"
BOARD="cpu_brd_v03_pba_260511"
PURPOSE="bringup-default"
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage:
  ./tools/prepare/sync-custom-board-dts-set-to-workspace.sh [linux|u-boot|all] [board] [purpose] [--dry-run]

Defaults:
  mode    : all
  board   : cpu_brd_v03_pba_260511
  purpose : bringup-default

Examples:
  ./tools/prepare/sync-custom-board-dts-set-to-workspace.sh --dry-run
  ./tools/prepare/sync-custom-board-dts-set-to-workspace.sh linux cpu_brd_v03_pba_260511 bringup-default
  ./tools/prepare/sync-custom-board-dts-set-to-workspace.sh u-boot cpu_brd_v03_pba_260511 bringup-default --dry-run
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        linux|u-boot|all)
            MODE="$1"
            ;;
        cpu_brd_v03_pba_260511)
            BOARD="$1"
            ;;
        bringup-default)
            PURPOSE="$1"
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unsupported argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

require_dir() {
    local path="$1"
    local label="$2"

    if [ ! -d "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

require_file() {
    local path="$1"
    local label="$2"

    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

is_allowed_dirty_path() {
    local candidate="$1"
    shift
    local allowed

    for allowed in "$@"; do
        if [ "$candidate" = "$allowed" ]; then
            return 0
        fi
    done

    return 1
}

ensure_workspace_repo_ready() {
    local repo_path="$1"
    local label="$2"
    shift 2
    local managed_paths=("$@")
    local dirty
    local line
    local path

    dirty="$(git -C "$repo_path" status --porcelain)"
    if [ -z "$dirty" ]; then
        return
    fi

    while IFS= read -r line; do
        [ -n "$line" ] || continue
        path="${line:3}"

        if ! is_allowed_dirty_path "$path" "${managed_paths[@]}"; then
            echo "[ERROR] $label has unmanaged dirty files. Sync helper refuses to modify it." >&2
            printf '%s\n' "$dirty" >&2
            exit 1
        fi
    done <<EOF
$dirty
EOF

    printf '[INFO] %s has only managed custom-board projection changes; continuing.\n' "$label"
}

kernel_managed_paths() {
    cat <<'EOF'
arch/arm64/boot/dts/ti/k3-am6412-cpu-brd-v03-pba.dts
arch/arm64/boot/dts/ti/k3-am6412-custom-final-overrides.dtsi
arch/arm64/boot/dts/ti/k3-am6412-custom-pinmux.facts.dtsi
arch/arm64/boot/dts/ti/Makefile
EOF
}

uboot_managed_paths() {
    cat <<'EOF'
dts/upstream/src/arm64/ti/k3-am6412-cpu-brd-v03-pba.dts
dts/upstream/src/arm64/ti/k3-am6412-custom-final-overrides.dtsi
dts/upstream/src/arm64/ti/k3-am6412-custom-pinmux.facts.dtsi
arch/arm/dts/k3-am6412-cpu-brd-v03-pba-u-boot.dtsi
arch/arm/dts/k3-am6412-custom-u-boot-spl.dtsi
arch/arm/dts/k3-am6412-custom-early-pinmux.facts.dtsi
arch/arm/dts/k3-am6412-cpu-brd-v03-pba-r5.dts
arch/arm/dts/k3-am64x-binman.dtsi
EOF
}

load_managed_paths() {
    local collector="$1"

    mapfile -t MANAGED_PATHS < <($collector)
}

check_kernel_workspace_ready() {
    load_managed_paths kernel_managed_paths
    ensure_workspace_repo_ready "$KERNEL_SRC" "Kernel workspace" "${MANAGED_PATHS[@]}"
}

check_uboot_workspace_ready() {
    load_managed_paths uboot_managed_paths
    ensure_workspace_repo_ready "$UBOOT_SRC" "U-Boot workspace" "${MANAGED_PATHS[@]}"
}

copy_file() {
    local src="$1"
    local dst="$2"

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN] copy %s -> %s\n' "$src" "$dst"
        return
    fi

    install -m 0644 "$src" "$dst"
}

write_text_file() {
    local dst="$1"
    local content="$2"

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN] write %s\n' "$dst"
        return
    fi

    printf '%s' "$content" > "$dst"
}

ensure_linux_makefile_entry() {
    local makefile="$1"
    local line="$2"

    require_file "$makefile" "Linux DTS Makefile"

    if grep -qxF "$line" "$makefile"; then
        printf '[INFO] Linux Makefile entry already present: %s\n' "$line"
        return
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN] append %s to %s\n' "$line" "$makefile"
        return
    fi

    printf '%s\n' "$line" >> "$makefile"
}

select_board_paths() {
    case "$BOARD:$PURPOSE" in
        cpu_brd_v03_pba_260511:bringup-default)
            LINUX_SET_DIR="$BRINGUP_ROOT/bsp/linux/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default"
            UBOOT_SET_DIR="$BRINGUP_ROOT/bsp/u-boot/dts/custom-board/cpu_brd_v03_pba_260511/sets/bringup-default"

            KERNEL_DTS_DIR="$KERNEL_SRC/arch/arm64/boot/dts/ti"
            KERNEL_MAKEFILE="$KERNEL_DTS_DIR/Makefile"
            KERNEL_TOPLEVEL_NAME="k3-am6412-cpu-brd-v03-pba.dts"
            KERNEL_TOPLEVEL_DTB="k3-am6412-cpu-brd-v03-pba.dtb"

            UBOOT_A53_DTS_DIR="$UBOOT_SRC/dts/upstream/src/arm64/ti"
            UBOOT_ARM_DTS_DIR="$UBOOT_SRC/arch/arm/dts"
            UBOOT_A53_TREE_NAME="ti/k3-am6412-cpu-brd-v03-pba"
            UBOOT_A53_TOPLEVEL_NAME="k3-am6412-cpu-brd-v03-pba.dts"
            UBOOT_R5_TREE_NAME="k3-am6412-cpu-brd-v03-pba-r5"
            UBOOT_R5_TOPLEVEL_NAME="k3-am6412-cpu-brd-v03-pba-r5.dts"
            UBOOT_BOARD_QUIRKS_NAME="k3-am6412-cpu-brd-v03-pba-u-boot.dtsi"
            UBOOT_TEMP_DDR_BASELINE="k3-am64-sk-lp4-1600MTs.dtsi"
            ;;
        *)
            echo "[ERROR] Unsupported board/purpose: $BOARD / $PURPOSE" >&2
            exit 1
            ;;
    esac
}

sync_linux() {
    require_dir "$KERNEL_SRC" "kernel workspace"
    require_dir "$KERNEL_DTS_DIR" "kernel DTS directory"
    require_dir "$LINUX_SET_DIR" "root-managed Linux DTS set"
    check_kernel_workspace_ready

    copy_file "$LINUX_SET_DIR/k3-am6412-custom-final.dts" "$KERNEL_DTS_DIR/$KERNEL_TOPLEVEL_NAME"
    copy_file "$LINUX_SET_DIR/k3-am6412-custom-final-overrides.dtsi" "$KERNEL_DTS_DIR/k3-am6412-custom-final-overrides.dtsi"
    copy_file "$LINUX_SET_DIR/k3-am6412-custom-pinmux.facts.dtsi" "$KERNEL_DTS_DIR/k3-am6412-custom-pinmux.facts.dtsi"
    ensure_linux_makefile_entry "$KERNEL_MAKEFILE" "dtb-\$(CONFIG_ARCH_K3) += $KERNEL_TOPLEVEL_DTB"
}

sync_uboot() {
    local r5_wrapper

    require_dir "$UBOOT_SRC" "U-Boot workspace"
    require_dir "$UBOOT_A53_DTS_DIR" "U-Boot A53 DTS directory"
    require_dir "$UBOOT_ARM_DTS_DIR" "U-Boot arch/arm DTS directory"
    require_dir "$LINUX_SET_DIR" "root-managed Linux DTS set"
    require_dir "$UBOOT_SET_DIR" "root-managed U-Boot DTS set"
    check_uboot_workspace_ready

    copy_file "$LINUX_SET_DIR/k3-am6412-custom-final.dts" "$UBOOT_A53_DTS_DIR/$UBOOT_A53_TOPLEVEL_NAME"
    copy_file "$LINUX_SET_DIR/k3-am6412-custom-final-overrides.dtsi" "$UBOOT_A53_DTS_DIR/k3-am6412-custom-final-overrides.dtsi"
    copy_file "$LINUX_SET_DIR/k3-am6412-custom-pinmux.facts.dtsi" "$UBOOT_A53_DTS_DIR/k3-am6412-custom-pinmux.facts.dtsi"

    copy_file "$UBOOT_SET_DIR/k3-am6412-custom-u-boot-final.dtsi" "$UBOOT_ARM_DTS_DIR/$UBOOT_BOARD_QUIRKS_NAME"
    copy_file "$UBOOT_SET_DIR/k3-am6412-custom-u-boot-spl.dtsi" "$UBOOT_ARM_DTS_DIR/k3-am6412-custom-u-boot-spl.dtsi"
    copy_file "$UBOOT_SET_DIR/k3-am6412-custom-early-pinmux.facts.dtsi" "$UBOOT_ARM_DTS_DIR/k3-am6412-custom-early-pinmux.facts.dtsi"

    r5_wrapper=$(cat <<EOF
// SPDX-License-Identifier: GPL-2.0
/*
 * Root-managed custom board R5/SPL wrapper for CPU_BRD_V03_PBA_260511.
 * Generated from root repo DTS set: $BOARD / $PURPOSE.
 * Temporary DDR baseline uses $UBOOT_TEMP_DDR_BASELINE until custom LPDDR4 timing source is finalized.
 */

#include "$UBOOT_A53_TOPLEVEL_NAME"
#include "$UBOOT_TEMP_DDR_BASELINE"
#include "k3-am64-ddr.dtsi"

#include "$UBOOT_BOARD_QUIRKS_NAME"
#include "k3-am642-r5.dtsi"
EOF
)

    write_text_file "$UBOOT_ARM_DTS_DIR/$UBOOT_R5_TOPLEVEL_NAME" "$r5_wrapper"
}

show_summary() {
    cat <<EOF
[INFO] Root-managed DTS set selection
  board   : $BOARD
  purpose : $PURPOSE
  mode    : $MODE

[INFO] Linux workspace projection
  source set : $LINUX_SET_DIR
  workspace  : $KERNEL_DTS_DIR/$KERNEL_TOPLEVEL_NAME
  Makefile   : $KERNEL_MAKEFILE adds $KERNEL_TOPLEVEL_DTB

[INFO] U-Boot workspace projection
  A53 DTS          : $UBOOT_A53_DTS_DIR/$UBOOT_A53_TOPLEVEL_NAME
  U-Boot quirks    : $UBOOT_ARM_DTS_DIR/$UBOOT_BOARD_QUIRKS_NAME
  R5 top-level DTS : $UBOOT_ARM_DTS_DIR/$UBOOT_R5_TOPLEVEL_NAME
  temp DDR include : $UBOOT_TEMP_DDR_BASELINE

[INFO] Recommended U-Boot config overrides for this DTS set
  A53:
    CONFIG_DEFAULT_DEVICE_TREE="$UBOOT_A53_TREE_NAME"
    CONFIG_OF_LIST="$UBOOT_A53_TREE_NAME"
  R5:
    CONFIG_DEFAULT_DEVICE_TREE="$UBOOT_R5_TREE_NAME"
    CONFIG_SPL_OF_LIST="$UBOOT_R5_TREE_NAME"

[INFO] Note
  U-Boot DTS source projection is prepared here, but final binman/package integration
  still needs review because current TI AM64x EVM packaging templates enumerate EVM/SK
  platform DT names explicitly.
EOF
}

select_board_paths

case "$MODE" in
    linux)
        sync_linux
        ;;
    u-boot)
        sync_uboot
        ;;
    all)
        sync_linux
        sync_uboot
        ;;
    *)
        echo "[ERROR] Unsupported mode: $MODE" >&2
        exit 1
        ;;
esac

show_summary
