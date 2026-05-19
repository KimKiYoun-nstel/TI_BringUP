#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ACTION="${1:-full}"
BOARD_IP="${2:-192.168.0.110}"

R5F_FW_LOCAL="$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw"
A53_BIN_LOCAL="$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/a53/sk_am64b_rpmsg_test_a53"
BOARD_FW_DIR="/usr/lib/firmware/mcusdk-benchmark_demo"
BOARD_FW_PATH="$BOARD_FW_DIR/am64-main-r5f0_0-fw"
BOARD_FW_BAK="$BOARD_FW_DIR/am64-main-r5f0_0-fw.ti_bringup_backup"
BOARD_FW_ORIG="$BOARD_FW_DIR/am64-main-r5f0_0-fw.ti_bringup_orig"
BOARD_A53_BIN="/usr/local/bin/sk_am64b_rpmsg_test_a53"

ssh_board() {
    ssh root@"$BOARD_IP" "$@"
}

wait_for_ssh() {
    local i
    for i in $(seq 1 30); do
        if ssh -o BatchMode=yes -o ConnectTimeout=5 root@"$BOARD_IP" "echo up" >/dev/null 2>&1; then
            return 0
        fi
        sleep 5
    done
    echo "[ERROR] Board did not come back: $BOARD_IP" >&2
    exit 1
}

build_if_needed() {
    if [ ! -f "$R5F_FW_LOCAL" ] || [ ! -f "$A53_BIN_LOCAL" ]; then
        "$BRINGUP_ROOT/tools/build/build-sk-am64b-rpmsg-test.sh" all
    fi
}

deploy_only() {
    build_if_needed
    ssh_board "mkdir -p /usr/local/bin"
    scp "$R5F_FW_LOCAL" root@"$BOARD_IP":"$BOARD_FW_PATH"
    scp "$A53_BIN_LOCAL" root@"$BOARD_IP":"$BOARD_A53_BIN"
    ssh_board "chmod +x '$BOARD_A53_BIN'"
}

backup_and_install() {
    build_if_needed
    ssh_board "if [ ! -f '$BOARD_FW_ORIG' ]; then cp -a '$BOARD_FW_PATH' '$BOARD_FW_ORIG'; fi; cp -a '$BOARD_FW_PATH' '$BOARD_FW_BAK'"
    ssh_board "systemctl stop rpmsg_json.service benchmark_server.service || true"
    ssh_board "mkdir -p /usr/local/bin"
    scp "$R5F_FW_LOCAL" root@"$BOARD_IP":"$BOARD_FW_PATH"
    scp "$A53_BIN_LOCAL" root@"$BOARD_IP":"$BOARD_A53_BIN"
    ssh_board "chmod +x '$BOARD_A53_BIN'; sync; reboot"
    wait_for_ssh
    sleep 12
}

run_test() {
    ssh_board "'$BOARD_A53_BIN' 'payload-from-a53'"
}

restore() {
    ssh_board "if [ -f '$BOARD_FW_ORIG' ]; then cp '$BOARD_FW_ORIG' '$BOARD_FW_PATH'; elif [ -f '$BOARD_FW_BAK' ]; then cp '$BOARD_FW_BAK' '$BOARD_FW_PATH'; fi; systemctl stop rpmsg_json.service benchmark_server.service || true; sync; reboot"
    wait_for_ssh
    sleep 12
    ssh_board "systemctl daemon-reload || true; systemctl start benchmark_server.service || true; systemctl restart rpmsg_json.service || true"
}

case "$ACTION" in
    deploy)
        deploy_only
        ;;
    run)
        run_test
        ;;
    restore)
        restore
        ;;
    full)
        trap 'restore' EXIT
        backup_and_install
        run_test
        trap - EXIT
        restore
        ;;
    *)
        echo "Usage: $0 {deploy|run|restore|full} [board-ip]" >&2
        exit 1
        ;;
esac
