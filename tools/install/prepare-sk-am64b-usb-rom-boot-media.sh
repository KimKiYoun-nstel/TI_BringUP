#!/usr/bin/env bash
set -euo pipefail

BOARD_IP="${1:-}"
DRY_RUN=0

SRC_DIR="/run/media/boot-mmcblk1p1"
ROMBOOT_DIR="/run/media/ROMBOOT-sda1"
BOOT_DIR="/run/media/BOOT-sda2"
BACKUP_DIR="$BOOT_DIR/backup/usb-rom-boot"

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/prepare-sk-am64b-usb-rom-boot-media.sh <board-ip> [--dry-run]

역할:
  - 현재 SD FAT root에서 proven bootloader trio를 읽는다.
  - USB ROMBOOT FAT root(sda1)에 tiboot3.bin / tispl.bin / u-boot.img 를 staging 한다.
  - USB BOOT FAT root(sda2)에도 같은 trio를 복제한다.
  - 기존 동일 파일이 있으면 backup 하에 덮어쓴다.

주의:
  - 이것은 USB Boot ROM mass-storage path를 위한 사전 staging이다.
  - 이 스크립트만으로 USB switch mode boot 성공이 보장되지는 않는다.
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

ssh_run "test -d '$SRC_DIR' && test -d '$ROMBOOT_DIR' && test -d '$BOOT_DIR'"
ssh_run "for f in tiboot3.bin tispl.bin u-boot.img; do test -f '$SRC_DIR/'\"\$f\" || { echo '[ERROR] missing source' \"\$f\"; exit 1; }; done"
ssh_run "mkdir -p '$BACKUP_DIR'; ts=\$(date +%Y%m%d-%H%M%S); for f in tiboot3.bin tispl.bin u-boot.img; do if [ -f '$ROMBOOT_DIR/'\"\$f\" ]; then cp '$ROMBOOT_DIR/'\"\$f\" '$BACKUP_DIR/'\"\$f\".romboot.\$ts; fi; if [ -f '$BOOT_DIR/'\"\$f\" ]; then cp '$BOOT_DIR/'\"\$f\" '$BACKUP_DIR/'\"\$f\".boot.\$ts; fi; cp '$SRC_DIR/'\"\$f\" '$ROMBOOT_DIR/'\"\$f\"; cp '$SRC_DIR/'\"\$f\" '$BOOT_DIR/'\"\$f\"; done; sync"
ssh_run "printf '\n--- USB ROMBOOT root after staging ---\n'; ls -lh '$ROMBOOT_DIR'; printf '\n--- USB BOOT root after staging ---\n'; ls -lh '$BOOT_DIR'; printf '\n--- checksums ---\n'; md5sum '$ROMBOOT_DIR/tiboot3.bin' '$ROMBOOT_DIR/tispl.bin' '$ROMBOOT_DIR/u-boot.img' '$BOOT_DIR/tiboot3.bin' '$BOOT_DIR/tispl.bin' '$BOOT_DIR/u-boot.img'"
