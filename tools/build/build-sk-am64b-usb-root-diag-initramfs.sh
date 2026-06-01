#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"
SDK_ENV_SETUP=""
SRC_DIR="$BRINGUP_ROOT/rootfs/initramfs/sk-am64b-usb-root-diag"
OUT_BASE="$BRINGUP_ROOT/out/initramfs/sk-am64b-usb-root-diag"
STAGE_DIR="$OUT_BASE/stage"
LOG_DIR="$OUT_BASE/logs"
BIN_OUT="$OUT_BASE/init"
CPIO_RAW="$OUT_BASE/sk-am64b-usb-root-diag.cpio"
CPIO_OUT="$OUT_BASE/sk-am64b-usb-root-diag.cpio.gz"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

SDK_ENV_SETUP="$LINUX_DEVKIT/environment-setup-aarch64-oe-linux"

if [ ! -f "$SDK_ENV_SETUP" ]; then
    echo "[ERROR] Missing SDK environment setup: $SDK_ENV_SETUP" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$SDK_ENV_SETUP"

read -r -a CC_CMD <<<"$CC"

if [ ! -f "$SRC_DIR/init.c" ]; then
    echo "[ERROR] Missing source: $SRC_DIR/init.c" >&2
    exit 1
fi

mkdir -p "$STAGE_DIR" "$LOG_DIR"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

"${CC_CMD[@]}" \
    -Os \
    -static \
    -Wall \
    -Wextra \
    -o "$BIN_OUT" \
    "$SRC_DIR/init.c" 2>&1 | tee "$LOG_DIR/build.log"

cp "$BIN_OUT" "$STAGE_DIR/init"
chmod 0755 "$STAGE_DIR/init"

(
    cd "$STAGE_DIR"
    find . -print0 | cpio --null -ov --format=newc > "$CPIO_RAW" 2> "$LOG_DIR/cpio.log"
)

gzip -n -9 -c "$CPIO_RAW" > "$CPIO_OUT"

ls -lh "$BIN_OUT" "$CPIO_OUT"
