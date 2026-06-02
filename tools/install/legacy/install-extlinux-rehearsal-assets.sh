#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-}"
TARGET="${2:-}"
DRY_RUN=0

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-extlinux-rehearsal-assets.sh <board-ip> <sd|usb|tftp> [--dry-run]

예:
  ./tools/install/install-extlinux-rehearsal-assets.sh 192.168.0.110 sd
  ./tools/install/install-extlinux-rehearsal-assets.sh 192.168.0.110 usb
  ./tools/install/install-extlinux-rehearsal-assets.sh 192.168.0.110 tftp
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

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        printf '[ERROR] Missing file: %s\n' "$path" >&2
        exit 1
    fi
}

if [ -z "$BOARD_IP" ] || [ -z "$TARGET" ]; then
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

case "$TARGET" in
    sd)
        SD_EXTLINUX_SRC="$BRINGUP_ROOT/boot-configs/extlinux/sd/extlinux.conf"
        require_file "$SD_EXTLINUX_SRC"
        ssh_run "mkdir -p /boot/extlinux"
        scp_to_board "$SD_EXTLINUX_SRC" "/boot/extlinux/extlinux.conf"
        ssh_run "sync && ls -al /boot/extlinux && sed -n '1,120p' /boot/extlinux/extlinux.conf"
        ;;
    usb)
        USB_EXTLINUX_SRC="$BRINGUP_ROOT/boot-configs/extlinux/usb/extlinux.conf"
        require_file "$USB_EXTLINUX_SRC"
        ssh_run "test -d /run/media/USB-BOOT-sda2 || { echo '[ERROR] USB-BOOT not mounted'; exit 1; }; mkdir -p /run/media/USB-BOOT-sda2/extlinux"
        ssh_run "cp /boot/Image /run/media/USB-BOOT-sda2/Image && cp /boot/dtb/ti/k3-am642-sk.dtb /run/media/USB-BOOT-sda2/k3-am642-sk.dtb"
        scp_to_board "$USB_EXTLINUX_SRC" "/run/media/USB-BOOT-sda2/extlinux/extlinux.conf"
        ssh_run "sync && ls -al /run/media/USB-BOOT-sda2 && ls -al /run/media/USB-BOOT-sda2/extlinux && sed -n '1,120p' /run/media/USB-BOOT-sda2/extlinux/extlinux.conf"
        ;;
    tftp)
        PXE_SRC="$BRINGUP_ROOT/boot-configs/extlinux/tftp/pxelinux.cfg.default"
        require_file "$PXE_SRC"
        mkdir -p "$BRINGUP_ROOT/tftp/pxelinux.cfg"
        cp "$PXE_SRC" "$BRINGUP_ROOT/tftp/pxelinux.cfg/default"
        ssh_run "true" >/dev/null 2>&1 || true
        printf 'Wrote %s\n' "$BRINGUP_ROOT/tftp/pxelinux.cfg/default"
        sed -n '1,120p' "$BRINGUP_ROOT/tftp/pxelinux.cfg/default"
        ;;
    *)
        printf '[ERROR] Unknown target: %s\n' "$TARGET" >&2
        usage >&2
        exit 1
        ;;
esac
