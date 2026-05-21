#!/usr/bin/env bash
set -euo pipefail

PATH='/usr/sbin:/usr/bin:/sbin:/bin'

ACTION="${1:-status}"
if [ "$#" -gt 0 ]; then
    shift
fi

FW_NAME="am64-main-r5f0_0-fw"
ACTIVE_FW_LINK="/usr/lib/firmware/${FW_NAME}"
TEST_FW_DIR="/usr/lib/firmware/ti-bringup/am64x-r5f-button-event-lab"
TEST_FW_PATH="${TEST_FW_DIR}/${FW_NAME}"
A53_APP="/usr/local/bin/r5ctl"

STATE_DIR="/var/lib/ti-bringup/am64x-r5f-button-event-lab"
ORIG_TARGET_FILE="${STATE_DIR}/${FW_NAME}.orig_target"
ORIG_COPY_FILE="${STATE_DIR}/${FW_NAME}.orig_copy"
LEGACY_ORIG_BACKUP="/usr/lib/firmware/mcusdk-benchmark_demo/${FW_NAME}.ti_bringup_orig"

BENCHMARK_SERVICES=(benchmark_server.service rpmsg_json.service)

log() {
    printf '[am64x-r5f-button-event-lab] %s\n' "$*"
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
    local current_target=""

    current_target="$(readlink -f "$ACTIVE_FW_LINK" 2>/dev/null || true)"
    if [ "$current_target" = "$target" ]; then
        log "test firmware already active: $target"
        return 0
    fi

    capture_orig_target
    require_path "$target"
    reboot_switch "$target"
}

restore_target() {
    local target
    local current_target=""

    require_path "$ORIG_TARGET_FILE"
    target="$(cat "$ORIG_TARGET_FILE")"
    current_target="$(readlink -f "$ACTIVE_FW_LINK" 2>/dev/null || true)"

    if [ "$current_target" = "$target" ]; then
        log "baseline firmware already active: $target"
        return 0
    fi
    if [ "$current_target" != "$TEST_FW_PATH" ]; then
        log "refusing restore: active target is neither test firmware nor saved baseline"
        log "active target: $current_target"
        log "saved baseline: $target"
        exit 1
    fi

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
    log "test firmware : $TEST_FW_PATH"
    log "benchmark_server.service : $(systemctl is-active benchmark_server.service || true)"
    log "rpmsg_json.service       : $(systemctl is-active rpmsg_json.service || true)"
}

test_command() {
    require_path "$A53_APP"
    if [ "$#" -eq 0 ]; then
        "$A53_APP" ping
    else
        "$A53_APP" "$@"
    fi
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
        test_command "$@"
        ;;
    *)
        log "usage: $0 {status|apply|restore|test} [r5ctl-args...]"
        log "examples: $0 test ping | $0 test status | $0 test button status | $0 test button wait 5000"
        exit 1
        ;;
esac
