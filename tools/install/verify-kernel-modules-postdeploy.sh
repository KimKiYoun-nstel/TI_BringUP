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
EXPECTED_RELEASE="${2:-}"

REQUIRED_MODULE_PATHS=(
    "kernel/drivers/remoteproc/ti_k3_r5_remoteproc.ko"
    "kernel/drivers/remoteproc/ti_k3_m4_remoteproc.ko"
    "kernel/drivers/rpmsg/rpmsg_char.ko"
    "kernel/drivers/rpmsg/rpmsg_ctrl.ko"
)

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/verify-kernel-modules-postdeploy.sh <board-ip> <expected-kernel-release>

예:
  ./tools/install/verify-kernel-modules-postdeploy.sh 192.168.0.110 6.18.13-gc21449208550
EOF
}

ssh_capture() {
    local cmd="$1"
    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
}

if [ -z "$BOARD_IP" ] || [ -z "$EXPECTED_RELEASE" ]; then
    usage >&2
    exit 1
fi

echo "[CHECK] uname -r"
REMOTE_UNAME="$(ssh_capture "uname -r")"
printf '%s\n' "$REMOTE_UNAME"
diff -u <(printf '%s\n' "$EXPECTED_RELEASE") <(printf '%s\n' "$REMOTE_UNAME")

echo "[CHECK] /lib/modules/$EXPECTED_RELEASE"
ssh_capture "test -d '/lib/modules/$EXPECTED_RELEASE' && ls '/lib/modules/$EXPECTED_RELEASE'"

echo "[CHECK] required module files"
for rel_path in "${REQUIRED_MODULE_PATHS[@]}"; do
    ssh_capture "test -f '/lib/modules/$EXPECTED_RELEASE/$rel_path' && ls -lh '/lib/modules/$EXPECTED_RELEASE/$rel_path'"
done

echo "[CHECK] modprobe resolution"
ssh_capture "modprobe -n -v ti_k3_r5_remoteproc"

echo "[INFO] Kernel modules post-deploy verification passed."
