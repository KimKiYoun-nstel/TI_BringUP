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

BOARD_IP="${1:-}"
MODE="${2:-}"

ARTIFACTS_DIR="$BRINGUP_ROOT/out/kernel/artifacts"
IMAGE_SRC="$ARTIFACTS_DIR/Image"
DTB_SRC="$ARTIFACTS_DIR/k3-am642-sk.dtb"
KERNEL_DST="/boot/Image"
DTB_DST="/boot/dtb/ti/k3-am642-sk.dtb"

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/verify-kernel-dtb-postdeploy.sh <board-ip> <all|image-only|dtb-only>

예:
  ./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 all
  ./tools/install/verify-kernel-dtb-postdeploy.sh 192.168.0.110 dtb-only
EOF
}

require_file() {
    local path="$1"
    local label="$2"

    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

ssh_capture() {
    local cmd="$1"
    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
}

if [ -z "$BOARD_IP" ] || [ -z "$MODE" ]; then
    usage >&2
    exit 1
fi

case "$MODE" in
    all|image-only|dtb-only)
        ;;
    *)
        echo "[ERROR] Unknown mode: $MODE" >&2
        usage >&2
        exit 1
        ;;
esac

LOCAL_SHA_FILE="$(mktemp)"
LOCAL_HASH_ONLY_FILE="$(mktemp)"
trap 'rm -f "$LOCAL_SHA_FILE" "$LOCAL_HASH_ONLY_FILE"' EXIT

case "$MODE" in
    all)
        require_file "$IMAGE_SRC" "kernel Image"
        require_file "$DTB_SRC" "baseline DTB"
        sha256sum "$IMAGE_SRC" "$DTB_SRC" > "$LOCAL_SHA_FILE"
        ;;
    image-only)
        require_file "$IMAGE_SRC" "kernel Image"
        sha256sum "$IMAGE_SRC" > "$LOCAL_SHA_FILE"
        ;;
    dtb-only)
        require_file "$DTB_SRC" "baseline DTB"
        sha256sum "$DTB_SRC" > "$LOCAL_SHA_FILE"
        ;;
esac

awk '{print $1}' "$LOCAL_SHA_FILE" > "$LOCAL_HASH_ONLY_FILE"

ssh_capture "true" >/dev/null

echo "[CHECK] uname -a"
ssh_capture "uname -a"

echo "[CHECK] /proc/cmdline"
ssh_capture "cat /proc/cmdline"

echo "[CHECK] /proc/device-tree/model"
ssh_capture "tr -d '\000' < /proc/device-tree/model"

case "$MODE" in
    all)
        REMOTE_SHA="$(ssh_capture "sha256sum '$KERNEL_DST' '$DTB_DST'")"
        ;;
    image-only)
        REMOTE_SHA="$(ssh_capture "sha256sum '$KERNEL_DST'")"
        ;;
    dtb-only)
        REMOTE_SHA="$(ssh_capture "sha256sum '$DTB_DST'")"
        ;;
esac

echo "[CHECK] checksum verify"
diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_SHA" | awk '{print $1}')

echo "[INFO] Post-deploy verification passed."
