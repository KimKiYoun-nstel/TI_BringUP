#!/usr/bin/env bash
set -euo pipefail

BOARD_IP="${1:-}"
DRY_RUN=0

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/prepare-usb-rehearsal-media.sh <board-ip> [--dry-run]

역할:
  - /dev/sda3 를 /mnt/usb-rootfs 에 mount
  - 현재 SD rootfs(/)를 USB rootfs로 tar 파이프 복사
  - /proc, /sys, /dev, /run, /tmp, /mnt, /media, /lost+found 제외
  - USB-BOOT(sda2)에 Image, DTB, extlinux.conf가 배치되도록 extlinux deploy script와 함께 사용
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

ssh_run "mkdir -p /mnt/usb-rootfs; mount /dev/sda3 /mnt/usb-rootfs"
ssh_run "cd / && tar cpf - --xattrs --acls --numeric-owner --one-file-system --exclude=./proc --exclude=./sys --exclude=./dev --exclude=./run --exclude=./tmp --exclude=./mnt --exclude=./media --exclude=./lost+found . | tar xpf - -C /mnt/usb-rootfs"
ssh_run "mkdir -p /mnt/usb-rootfs/proc /mnt/usb-rootfs/sys /mnt/usb-rootfs/dev /mnt/usb-rootfs/run /mnt/usb-rootfs/tmp && chmod 1777 /mnt/usb-rootfs/tmp"
ssh_run "sync && findmnt /mnt/usb-rootfs && ls -al /mnt/usb-rootfs | sed -n '1,80p'"
