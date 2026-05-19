#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
PAYLOAD="${2:-payload-from-a53}"

FW_NAME="am64-main-r5f0_0-fw"
ACTIVE_FW_LINK="/usr/lib/firmware/${FW_NAME}"
TEST_FW_DIR="/usr/lib/firmware/ti-bringup/sk-am64b-rpmsg-test"
TEST_FW_PATH="${TEST_FW_DIR}/${FW_NAME}"
A53_APP="/usr/local/bin/sk_am64b_rpmsg_test_a53"

STATE_DIR="/var/lib/ti-bringup/sk-am64b-rpmsg-test"
ORIG_TARGET_FILE="${STATE_DIR}/${FW_NAME}.orig_target"
ORIG_COPY_FILE="${STATE_DIR}/${FW_NAME}.orig_copy"
LEGACY_ORIG_BACKUP="/usr/lib/firmware/mcusdk-benchmark_demo/${FW_NAME}.ti_bringup_orig"

BENCHMARK_SERVICES=(benchmark_server.service rpmsg_json.service)

log() {
    printf '[sk-am64b-rpmsg-manage] %s\n' "$*"
}

require_path() {
    local path="$1"
    if [ ! -e "$path" ]; then
        log "missing required path: $path"
        exit 1
    fi
}

capture_orig_target() {
    mkdir -p "$STATE_DIR"
    if [ ! -f "$ORIG_TARGET_FILE" ]; then
        readlink -f "$ACTIVE_FW_LINK" > "$ORIG_TARGET_FILE"
    fi
    if [ ! -f "$ORIG_COPY_FILE" ]; then
        if [ -f "$LEGACY_ORIG_BACKUP" ]; then
            cp -a "$LEGACY_ORIG_BACKUP" "$ORIG_COPY_FILE"
        else
            cp -a "$(cat "$ORIG_TARGET_FILE")" "$ORIG_COPY_FILE"
        fi
    fi
}

stop_baseline_services() {
    local svc
    for svc in "${BENCHMARK_SERVICES[@]}"; do
        systemctl stop "$svc" || true
    done
}

start_baseline_services() {
    local svc
    for svc in "${BENCHMARK_SERVICES[@]}"; do
        systemctl start "$svc" || true
    done
}

switch_link() {
    local target="$1"
    ln -sfn "$target" "$ACTIVE_FW_LINK"
    sync
}

reboot_switch() {
    local target="$1"
    stop_baseline_services
    switch_link "$target"
    reboot
}

apply_target() {
    local target="$1"
    capture_orig_target
    require_path "$target"
    reboot_switch "$target"
}

restore_target() {
    local target
    require_path "$ORIG_TARGET_FILE"
    target="$(cat "$ORIG_TARGET_FILE")"
    if [ ! -f "$ORIG_COPY_FILE" ] && [ -f "$LEGACY_ORIG_BACKUP" ]; then
        mkdir -p "$STATE_DIR"
        cp -a "$LEGACY_ORIG_BACKUP" "$ORIG_COPY_FILE"
    fi
    require_path "$ORIG_COPY_FILE"

    cp -a "$ORIG_COPY_FILE" "$target"

    switch_link "$target"
    start_baseline_services
    reboot
}

status() {
    local target=""
    target="$(readlink -f "$ACTIVE_FW_LINK" 2>/dev/null || true)"

    log "active link   : $ACTIVE_FW_LINK"
    log "active target : $target"
    log "benchmark_server.service : $(systemctl is-active benchmark_server.service || true)"
    log "rpmsg_json.service       : $(systemctl is-active rpmsg_json.service || true)"
}

test_payload() {
    require_path "$A53_APP"
    "$A53_APP" "$PAYLOAD"
}

case "$ACTION" in
    status)
        status
        ;;
    apply)
        apply_target "$TEST_FW_PATH"
        ;;
    restore)
        restore_target
        ;;
    test)
        test_payload
        ;;
    *)
        log "usage: $0 {status|apply|restore|test} [payload]"
        exit 1
        ;;
esac
