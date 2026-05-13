#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -d "$KERNEL_SRC" ]; then
    echo "[ERROR] KERNEL_SRC not found: $KERNEL_SRC" >&2
    exit 1
fi

cd "$KERNEL_SRC"

export ARCH=arm64
export CROSS_COMPILE="$CROSS_COMPILE_AARCH64"

# Do not source linux-devkit/environment-setup for kernel standalone builds
# unless the SDK documentation for this exact version explicitly requires it.
mkdir -p "$BRINGUP_ROOT/out/kernel"

# TODO: Replace defconfig with the exact TI SDK defconfig if different.
make defconfig
make -j"$(nproc)" Image dtbs modules

echo "[INFO] Kernel build done."
echo "[INFO] Image: $KERNEL_SRC/arch/arm64/boot/Image"
echo "[INFO] DTBs:  $KERNEL_SRC/arch/arm64/boot/dts/ti/*.dtb"
