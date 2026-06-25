#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ -n "${UBOOT_SRC_OVERRIDE:-}" ]; then
    UBOOT_SRC="$UBOOT_SRC_OVERRIDE"
fi

if [ -n "${KERNEL_SRC_OVERRIDE:-}" ]; then
    KERNEL_SRC="$KERNEL_SRC_OVERRIDE"
fi

status=0

check_git_workspace() {
    local name="$1"
    local path="$2"
    local series="$3"
    local allow_dirty="${ALLOW_DIRTY_WORKSPACE:-0}"

    if [ ! -d "$path/.git" ] && [ ! -f "$path/.git" ]; then
        echo "[ERROR] Missing workspace git repo: $name ($path)" >&2
        status=1
        return
    fi

    if git -C "$path" diff --quiet; then
        echo "[OK] $name workspace has no unstaged diff"
    else
        if [ "$allow_dirty" = "1" ] || [ "$allow_dirty" = "$name" ]; then
            echo "[WARN] $name workspace has unstaged diff but ALLOW_DIRTY_WORKSPACE=1: $path" >&2
            return
        fi
        echo "[WARN] $name workspace has unstaged diff: $path" >&2
        echo "[ERROR] Export or discard workspace changes before build/deploy: $path" >&2
        if [ ! -f "$series" ]; then
            echo "[ERROR] Missing series file for $name: $series" >&2
        fi
        status=1
    fi
}

check_forbidden_external_sdk_edits() {
    local path="$1"

    if [ ! -f "$path" ]; then
        return
    fi

    if perl -0ne 'exit((/TISCI_DEV_MCU_MCU_GPIOMUX_INTROUTER0, TISCI_RESASG_SUBTYPE_IR_OUTPUT\),\n\s*\.start_resource = 0,\n\s*\.host_id = TISCI_HOST_ID_MAIN_0_R5_1,/s) ? 0 : 1)' "$path"; then
        echo "[WARN] External SDK file contains forbidden direct MCU GPIOMUX ownership rewrite: $path" >&2
        status=1
    fi
}

check_git_workspace "u-boot" "$UBOOT_SRC" "$BRINGUP_ROOT/bsp/u-boot/patches/series"
check_git_workspace "linux" "$KERNEL_SRC" "$BRINGUP_ROOT/bsp/linux/patches/series"

# Current known contamination pattern from the Phase2 incident.
check_forbidden_external_sdk_edits \
    "/home/nstel/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm.c"
check_forbidden_external_sdk_edits \
    "/home/nstel/ti/am64x/mcu_plus_sdk_am64x_12_00_00_27/source/drivers/sciclient/sciclient_default_boardcfg/am64x/sciclient_defaultBoardcfg_rm_linux.c"

if [ $status -ne 0 ]; then
    cat <<'EOF' >&2
[FAIL] Workspace state verification failed.

Meaning:
- there are workspace edits that still need repo-managed export, or
- forbidden external SDK modifications are still present.

Next steps:
1. export meaningful workspace diffs into bsp/*/patches/
2. recover any direct external SDK edits into repo-managed assets
3. restore external SDK originals to clean baseline
EOF
    exit $status
fi

echo "[OK] Workspace state verification passed."
