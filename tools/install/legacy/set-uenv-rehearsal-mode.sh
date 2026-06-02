#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-}"
MODE="${2:-}"
DRY_RUN=0
BOOT_DIR="/run/media/boot-mmcblk1p1"
BACKUP_DIR="$BOOT_DIR/backup/uenv"

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/set-uenv-rehearsal-mode.sh <board-ip> <baseline|sd-extlinux|usb-extlinux|usb-manual|pxe> [--dry-run]

예:
  ./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 sd-extlinux
  ./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 usb-extlinux
  ./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 usb-manual
  ./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 pxe
  ./tools/install/set-uenv-rehearsal-mode.sh 192.168.0.110 baseline
EOF
}

ssh_run() {
    local cmd="$1"
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN][ssh] %s\n' "$cmd"
        return 0
    fi
    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
}

scp_to_board() {
    local src="$1"
    local dst="$2"
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[DRY-RUN][scp] %s -> root@%s:%s\n' "$src" "$BOARD_IP" "$dst"
        return 0
    fi
    scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$src" "root@$BOARD_IP:$dst"
}

if [ -z "$BOARD_IP" ] || [ -z "$MODE" ]; then
    usage >&2
    exit 1
fi

shift 2 || true

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf '[ERROR] Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

case "$MODE" in
    baseline)
        TEMPLATE="$BRINGUP_ROOT/boot-configs/uenv/baseline-empty.uEnv.txt"
        ;;
    sd-extlinux)
        TEMPLATE="$BRINGUP_ROOT/boot-configs/uenv/sd-extlinux.uEnv.txt"
        ;;
    usb-extlinux)
        TEMPLATE="$BRINGUP_ROOT/boot-configs/uenv/usb-extlinux.uEnv.txt"
        ;;
    usb-manual)
        TEMPLATE="$BRINGUP_ROOT/boot-configs/uenv/usb-manual-load.uEnv.txt"
        ;;
    pxe)
        TEMPLATE="$BRINGUP_ROOT/boot-configs/uenv/pxe-rehearsal.uEnv.txt"
        ;;
    *)
        printf '[ERROR] Unknown mode: %s\n' "$MODE" >&2
        usage >&2
        exit 1
        ;;
esac

if [ ! -f "$TEMPLATE" ]; then
    printf '[ERROR] Missing template: %s\n' "$TEMPLATE" >&2
    exit 1
fi

ssh_run "mkdir -p '$BACKUP_DIR'; ts=\$(date +%Y%m%d-%H%M%S); cp '$BOOT_DIR/uEnv.txt' '$BACKUP_DIR/uEnv.txt.'\$ts"
scp_to_board "$TEMPLATE" "$BOOT_DIR/uEnv.txt"
ssh_run "sync && printf '\n--- active uEnv.txt ---\n' && sed -n '1,120p' '$BOOT_DIR/uEnv.txt'"
