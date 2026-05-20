#!/usr/bin/env bash
set -euo pipefail

BOARD_IP="${1:-192.168.0.110}"
ACTION="${2:-status}"
KNOWN_HOSTS_DIR="/tmp/opencode/ssh"
KNOWN_HOSTS_FILE="$KNOWN_HOSTS_DIR/sk-am64b_known_hosts"
LAB_SERVICES=(benchmark_server.service rpmsg_json.service)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OVERLAY_ROOT="$BRINGUP_ROOT/rootfs/overlays/sk-am64b-lab-r5f"

prepare_known_hosts() {
    mkdir -p "$KNOWN_HOSTS_DIR"
    ssh-keyscan -T 10 "$BOARD_IP" > "$KNOWN_HOSTS_FILE"
    chmod 600 "$KNOWN_HOSTS_FILE"
}

board_ssh() {
    ssh \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
        root@"$BOARD_IP" "$@"
}

show_status() {
    board_ssh '
        printf "== service state ==\n"
        systemctl is-enabled benchmark_server.service rpmsg_json.service || true
        systemctl is-active benchmark_server.service rpmsg_json.service || true
        printf "\n== lab marker ==\n"
        ls -l /etc/ti-bringup/lab-r5f.mode 2>/dev/null || true
        printf "\n== unit files ==\n"
        systemctl cat benchmark_server.service 2>/dev/null || true
        printf "\n"
        systemctl cat rpmsg_json.service 2>/dev/null || true
    '
}

deploy_overlay_policy() {
    board_ssh 'mkdir -p /etc/ti-bringup /etc/systemd/system/benchmark_server.service.d /etc/systemd/system/rpmsg_json.service.d'
    scp \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
        "$OVERLAY_ROOT/etc/ti-bringup/lab-r5f.mode" \
        root@"$BOARD_IP":/etc/ti-bringup/lab-r5f.mode
    scp \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
        "$OVERLAY_ROOT/etc/systemd/system/benchmark_server.service.d/lab-mode.conf" \
        root@"$BOARD_IP":/etc/systemd/system/benchmark_server.service.d/lab-mode.conf
    scp \
        -o BatchMode=yes \
        -o ConnectTimeout=10 \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$KNOWN_HOSTS_FILE" \
        "$OVERLAY_ROOT/etc/systemd/system/rpmsg_json.service.d/lab-mode.conf" \
        root@"$BOARD_IP":/etc/systemd/system/rpmsg_json.service.d/lab-mode.conf
    board_ssh '
        systemctl enable benchmark_server.service rpmsg_json.service
        systemctl daemon-reload
        systemctl stop benchmark_server.service rpmsg_json.service || true
        printf "== after overlay apply ==\n"
        systemctl is-enabled benchmark_server.service rpmsg_json.service || true
        systemctl is-active benchmark_server.service rpmsg_json.service || true
        ls -l /etc/ti-bringup/lab-r5f.mode
    '
}

remove_overlay_policy() {
    board_ssh '
        rm -f /etc/ti-bringup/lab-r5f.mode
        rm -f /etc/systemd/system/benchmark_server.service.d/lab-mode.conf
        rm -f /etc/systemd/system/rpmsg_json.service.d/lab-mode.conf
        systemctl daemon-reload
        systemctl enable --now benchmark_server.service rpmsg_json.service || true
        printf "== after overlay remove ==\n"
        systemctl is-enabled benchmark_server.service rpmsg_json.service || true
        systemctl is-active benchmark_server.service rpmsg_json.service || true
    '
}

apply_lab_mode() {
    board_ssh '
        systemctl disable --now benchmark_server.service rpmsg_json.service
        printf "== after disable --now ==\n"
        systemctl is-enabled benchmark_server.service rpmsg_json.service || true
        systemctl is-active benchmark_server.service rpmsg_json.service || true
    '
}

restore_baseline_mode() {
    board_ssh '
        systemctl enable --now benchmark_server.service rpmsg_json.service
        printf "== after enable --now ==\n"
        systemctl is-enabled benchmark_server.service rpmsg_json.service || true
        systemctl is-active benchmark_server.service rpmsg_json.service || true
    '
}

usage() {
    cat <<EOF
Usage: $0 [BOARD_IP] {status|apply|restore}

Examples:
  $0 192.168.0.110 status
  $0 192.168.0.110 apply
  $0 192.168.0.110 restore
  $0 192.168.0.110 overlay-apply
  $0 192.168.0.110 overlay-restore

Meaning:
  status  - show current baseline service policy and unit definitions
  apply   - disable --now benchmark_server.service and rpmsg_json.service
  restore - enable --now benchmark_server.service and rpmsg_json.service
  overlay-apply   - install repo-managed lab overlay marker/drop-ins and keep services enabled-but-skipped at boot
  overlay-restore - remove repo-managed lab overlay marker/drop-ins and restore baseline autostart
EOF
}

prepare_known_hosts

case "$ACTION" in
    status)
        show_status
        ;;
    apply)
        apply_lab_mode
        ;;
    restore)
        restore_baseline_mode
        ;;
    overlay-apply)
        deploy_overlay_policy
        ;;
    overlay-restore)
        remove_overlay_policy
        ;;
    *)
        usage
        exit 1
        ;;
esac
