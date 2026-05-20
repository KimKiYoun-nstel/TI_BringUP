#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-192.168.0.110}"
PROJECT_SLUG="am64x-r5f-hw-control-lab"

R5F_FW_LOCAL="$BRINGUP_ROOT/out/$PROJECT_SLUG/am64-main-r5f0_0-fw"
A53_BIN_LOCAL="$BRINGUP_ROOT/out/$PROJECT_SLUG/a53/r5ctl"
BOARD_SCRIPT_LOCAL="$BRINGUP_ROOT/projects/$PROJECT_SLUG/board/am64x-r5f-hw-control-lab-manage.sh"

BOARD_FW_DIR="/usr/lib/firmware/ti-bringup/$PROJECT_SLUG"
BOARD_FW_PATH="$BOARD_FW_DIR/am64-main-r5f0_0-fw"
BOARD_A53_BIN="/usr/local/bin/r5ctl"
BOARD_MANAGE_SCRIPT="/usr/local/sbin/am64x-r5f-hw-control-lab-manage.sh"

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

require_file "$R5F_FW_LOCAL"
require_file "$A53_BIN_LOCAL"
require_file "$BOARD_SCRIPT_LOCAL"

ssh root@"$BOARD_IP" "mkdir -p '$BOARD_FW_DIR' /usr/local/bin /usr/local/sbin"

scp "$R5F_FW_LOCAL" root@"$BOARD_IP":"$BOARD_FW_PATH"
scp "$A53_BIN_LOCAL" root@"$BOARD_IP":"$BOARD_A53_BIN"
scp "$BOARD_SCRIPT_LOCAL" root@"$BOARD_IP":"$BOARD_MANAGE_SCRIPT"

ssh root@"$BOARD_IP" "chmod +x '$BOARD_A53_BIN' '$BOARD_MANAGE_SCRIPT'; ls -l '$BOARD_FW_PATH' '$BOARD_A53_BIN' '$BOARD_MANAGE_SCRIPT'"
