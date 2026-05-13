#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

mkdir -p "$WORKSPACE_ROOT"

if [ ! -d "$SDK_ROOT" ]; then
    echo "[ERROR] SDK_ROOT not found: $SDK_ROOT" >&2
    exit 1
fi

if [ ! -d "$UBOOT_SDK_SRC" ]; then
    echo "[ERROR] UBOOT_SDK_SRC not found: $UBOOT_SDK_SRC" >&2
    exit 1
fi

if [ ! -d "$KERNEL_SDK_SRC" ]; then
    echo "[ERROR] KERNEL_SDK_SRC not found: $KERNEL_SDK_SRC" >&2
    exit 1
fi

if [ ! -d "$UBOOT_SRC" ]; then
    echo "[INFO] Creating U-Boot workspace: $UBOOT_SRC"
    cp -a "$UBOOT_SDK_SRC" "$UBOOT_SRC"
else
    echo "[INFO] U-Boot workspace already exists: $UBOOT_SRC"
fi

if [ ! -d "$KERNEL_SRC" ]; then
    echo "[INFO] Creating Linux kernel workspace: $KERNEL_SRC"
    cp -a "$KERNEL_SDK_SRC" "$KERNEL_SRC"
else
    echo "[INFO] Linux kernel workspace already exists: $KERNEL_SRC"
fi

echo "[INFO] Workspace ready."
echo "[INFO] UBOOT_SRC=$UBOOT_SRC"
echo "[INFO] KERNEL_SRC=$KERNEL_SRC"
