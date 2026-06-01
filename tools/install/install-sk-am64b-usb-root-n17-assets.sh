#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BOARD_IP="${1:-}"
DRY_RUN=0

KERNEL_SRC="$BRINGUP_ROOT/out/kernel-usb-boot/artifacts/Image"
DTB_SRC="$BRINGUP_ROOT/out/kernel-usb-boot/artifacts/k3-am642-sk-usb-root.dtb"
INITRAMFS_SRC="$BRINGUP_ROOT/out/initramfs/sk-am64b-usb-root-diag/sk-am64b-usb-root-diag.cpio.gz"

USB_BOOT_DIR="/run/media/BOOT-sda2/boot"
USB_DTB_DIR="$USB_BOOT_DIR/dtb/ti"
SD_BOOT_DIR="/boot"

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-sk-am64b-usb-root-n17-assets.sh <board-ip> [--dry-run]

역할:
  - USB boot sample로 사용할 `/boot/Image.usbtest` 갱신
  - USB boot sample로 사용할 `k3-am642-sk-usb-root.dtb` 갱신
  - SD rootfs `/boot/sk-am64b-usb-root-diag.cpio.gz` 갱신
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

require_file "$KERNEL_SRC"
require_file "$DTB_SRC"
require_file "$INITRAMFS_SRC"

ssh_run "test -d '$USB_BOOT_DIR' && test -d '$USB_DTB_DIR' && test -d '$SD_BOOT_DIR'"

scp_to_board "$KERNEL_SRC" "$USB_BOOT_DIR/Image.usbtest"
scp_to_board "$DTB_SRC" "$USB_DTB_DIR/k3-am642-sk-usb-root.dtb"
scp_to_board "$INITRAMFS_SRC" "$SD_BOOT_DIR/sk-am64b-usb-root-diag.cpio.gz"

ssh_run "sync && ls -lh '$USB_BOOT_DIR/Image.usbtest' '$USB_DTB_DIR/k3-am642-sk-usb-root.dtb' '$SD_BOOT_DIR/sk-am64b-usb-root-diag.cpio.gz' && md5sum '$USB_BOOT_DIR/Image.usbtest' '$USB_DTB_DIR/k3-am642-sk-usb-root.dtb' '$SD_BOOT_DIR/sk-am64b-usb-root-diag.cpio.gz'"
