#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-192.168.0.110}"

R5F_FW_LOCAL="$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw"
A53_BIN_LOCAL="$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/a53/sk_am64b_rpmsg_test_a53"
BOARD_SCRIPT_LOCAL="$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/board/sk-am64b-rpmsg-manage.sh"

BOARD_FW_DIR="/usr/lib/firmware/ti-bringup/sk-am64b-rpmsg-test"
BOARD_FW_PATH="$BOARD_FW_DIR/am64-main-r5f0_0-fw"
BOARD_A53_BIN="/usr/local/bin/sk_am64b_rpmsg_test_a53"
BOARD_MANAGE_SCRIPT="/usr/local/sbin/sk-am64b-rpmsg-manage.sh"

ssh root@"$BOARD_IP" "mkdir -p '$BOARD_FW_DIR' /usr/local/bin /usr/local/sbin"

scp "$R5F_FW_LOCAL" root@"$BOARD_IP":"$BOARD_FW_PATH"
scp "$A53_BIN_LOCAL" root@"$BOARD_IP":"$BOARD_A53_BIN"
scp "$BOARD_SCRIPT_LOCAL" root@"$BOARD_IP":"$BOARD_MANAGE_SCRIPT"

ssh root@"$BOARD_IP" "chmod +x '$BOARD_A53_BIN' '$BOARD_MANAGE_SCRIPT'; ls -l '$BOARD_FW_PATH' '$BOARD_A53_BIN' '$BOARD_MANAGE_SCRIPT'"
