#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-}"
DRY_RUN=0
SRC="$BRINGUP_ROOT/out/initramfs/sk-am64b-usb-root-diag/sk-am64b-usb-root-diag.cpio.gz"
DST_DIR="/boot"
DST_FILE="$DST_DIR/sk-am64b-usb-root-diag.cpio.gz"

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-sk-am64b-usb-root-diag-initramfs.sh <board-ip> [--dry-run]

예:
  ./tools/install/install-sk-am64b-usb-root-diag-initramfs.sh 192.168.0.110
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

if [ -z "$BOARD_IP" ]; then
    usage >&2
    exit 1
fi

shift || true

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

if [ ! -f "$SRC" ]; then
    printf '[ERROR] Missing initramfs artifact: %s\n' "$SRC" >&2
    exit 1
fi

ssh_run "test -d '$DST_DIR'"
scp_to_board "$SRC" "$DST_FILE"
ssh_run "sync && ls -lh '$DST_FILE' && md5sum '$DST_FILE'"
