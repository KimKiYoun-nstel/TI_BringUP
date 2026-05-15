#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

PREBUILT_DIR="$PREBUILT_IMAGES/am64xx-evm"

check_contamination_var() {
    local name="$1"

    if [ -n "${!name:-}" ]; then
        echo "[WARN] Environment contamination risk: $name is set." >&2
    fi
}

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

require_command() {
    local path="$1"
    local label="$2"

    if [ ! -x "$path" ]; then
        echo "[ERROR] Missing executable $label: $path" >&2
        exit 1
    fi
}

require_dir "$SDK_ROOT" "SDK root"
require_dir "$BOARD_SUPPORT" "board-support directory"
require_dir "$LINUX_DEVKIT" "linux-devkit"
require_dir "$K3R5_DEVKIT" "k3r5-devkit"
require_dir "$UBOOT_SRC/.git" "U-Boot workspace git repository"
require_dir "$KERNEL_SRC/.git" "kernel workspace git repository"
require_dir "$PREBUILT_IMAGES" "prebuilt-images directory"
require_dir "$PREBUILT_DIR" "AM64x prebuilt image directory"

if [ "$UBOOT_SRC" = "$UBOOT_SDK_SRC" ]; then
    echo "[ERROR] UBOOT_SRC points to SDK reference source, not workspace: $UBOOT_SRC" >&2
    exit 1
fi

if [ "$KERNEL_SRC" = "$KERNEL_SDK_SRC" ]; then
    echo "[ERROR] KERNEL_SRC points to SDK reference source, not workspace: $KERNEL_SRC" >&2
    exit 1
fi

case "$UBOOT_SRC" in
    "$WORKSPACE_ROOT"/*) ;;
    *)
        echo "[ERROR] UBOOT_SRC is outside workspace/: $UBOOT_SRC" >&2
        exit 1
        ;;
esac

case "$KERNEL_SRC" in
    "$WORKSPACE_ROOT"/*) ;;
    *)
        echo "[ERROR] KERNEL_SRC is outside workspace/: $KERNEL_SRC" >&2
        exit 1
        ;;
esac

require_file "$PREBUILT_DIR/bl31.bin" "TF-A BL31 binary"
require_file "$PREBUILT_DIR/bl32.bin" "OP-TEE BL32 binary"
require_command "${CROSS_COMPILE_AARCH64}gcc" "AArch64 GCC"
require_command "${CROSS_COMPILE_ARMV7R}gcc" "ARM R5 GCC"

check_contamination_var OECORE_NATIVE_SYSROOT
check_contamination_var OECORE_TARGET_SYSROOT
check_contamination_var SDKTARGETSYSROOT
check_contamination_var CONFIG_SITE
check_contamination_var PYTHONHOME
check_contamination_var PYTHONPATH
check_contamination_var CC
check_contamination_var CFLAGS
check_contamination_var LDFLAGS

printf 'BRINGUP_ROOT=%s\n' "$BRINGUP_ROOT"
printf 'SDK_ROOT=%s\n' "$SDK_ROOT"
printf 'UBOOT_SRC=%s\n' "$UBOOT_SRC"
printf 'KERNEL_SRC=%s\n' "$KERNEL_SRC"
printf 'PREBUILT_IMAGES=%s\n' "$PREBUILT_IMAGES"
printf 'PREBUILT_DIR=%s\n' "$PREBUILT_DIR"

printf 'AARCH64_GCC=%s\n' "$("${CROSS_COMPILE_AARCH64}gcc" --version | sed -n '1p')"
printf 'ARMV7R_GCC=%s\n' "$("${CROSS_COMPILE_ARMV7R}gcc" --version | sed -n '1p')"

printf 'UBOOT_HEAD=%s\n' "$(git -C "$UBOOT_SRC" rev-parse HEAD)"
printf 'UBOOT_BRANCH=%s\n' "$(git -C "$UBOOT_SRC" rev-parse --abbrev-ref HEAD)"
printf 'UBOOT_TAGS=%s\n' "$(git -C "$UBOOT_SRC" tag --points-at HEAD | paste -sd ',' - || true)"

printf 'KERNEL_HEAD=%s\n' "$(git -C "$KERNEL_SRC" rev-parse HEAD)"
printf 'KERNEL_BRANCH=%s\n' "$(git -C "$KERNEL_SRC" rev-parse --abbrev-ref HEAD)"
printf 'KERNEL_TAGS=%s\n' "$(git -C "$KERNEL_SRC" tag --points-at HEAD | paste -sd ',' - || true)"

if [ -n "$(git -C "$UBOOT_SRC" status --short)" ]; then
    echo "[WARN] U-Boot workspace is dirty." >&2
    git -C "$UBOOT_SRC" status --short
fi

if [ -n "$(git -C "$KERNEL_SRC" status --short)" ]; then
    echo "[WARN] Kernel workspace is dirty." >&2
    git -C "$KERNEL_SRC" status --short
fi

echo "[INFO] Environment validation passed."
