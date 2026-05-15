#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

BOARD_IP="${1:-}"
REBOOT_AFTER=0
DRY_RUN=0
BOOT_DIR="/run/media/boot-mmcblk1p1"
SRC_DIR="$BRINGUP_ROOT/out/u-boot/artifacts"
FILES=(tiboot3.bin tispl.bin u-boot.img)
LOCAL_SHA_FILE=""
LOCAL_HASH_ONLY_FILE=""
BACKUP_KEEP_COUNT=3

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-bootloader-to-sd.sh <board-ip> [--reboot] [--dry-run]

예:
  ./tools/install/install-bootloader-to-sd.sh 192.168.0.110
  ./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --reboot
  ./tools/install/install-bootloader-to-sd.sh 192.168.0.110 --dry-run
EOF
}

require_file() {
    local path="$1"
    local label="$2"

    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

ssh_run() {
    local cmd="$1"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN][ssh] $cmd"
        return 0
    fi

    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
}

ssh_capture() {
    local cmd="$1"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN][ssh-capture] $cmd"
        return 0
    fi

    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
}

scp_to_board() {
    local src="$1"
    local dst="$2"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN][scp] $src -> root@$BOARD_IP:$dst"
        return 0
    fi

    scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$src" "root@$BOARD_IP:$dst"
}

cleanup_local_tempfiles() {
    rm -f "${LOCAL_SHA_FILE:-}" "${LOCAL_HASH_ONLY_FILE:-}"
}

cleanup_remote_backup_retention() {
    local backup_parent="$1"

    ssh_run "if [ -d '$backup_parent' ]; then ls -1dt '$backup_parent'/* 2>/dev/null | tail -n +$((BACKUP_KEEP_COUNT + 1)) | xargs -r rm -rf; fi"
}

cleanup_remote_stage_on_success() {
    local stage_dir="$1"

    ssh_run "rm -rf '$stage_dir'"
}

trap cleanup_local_tempfiles EXIT

if [ -z "$BOARD_IP" ]; then
    usage >&2
    exit 1
fi

shift || true

while [ "$#" -gt 0 ]; do
    case "$1" in
        --reboot)
            REBOOT_AFTER=1
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

for file in "${FILES[@]}"; do
    require_file "$SRC_DIR/$file" "$file artifact"
done

LOCAL_SHA_FILE="$(mktemp)"
LOCAL_HASH_ONLY_FILE="$(mktemp)"
sha256sum "$SRC_DIR/tiboot3.bin" "$SRC_DIR/tispl.bin" "$SRC_DIR/u-boot.img" > "$LOCAL_SHA_FILE"
awk '{print $1}' "$LOCAL_SHA_FILE" > "$LOCAL_HASH_ONLY_FILE"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="/tmp/ti-bringup-uboot-$TIMESTAMP"
REMOTE_BACKUP="$BOOT_DIR/backup/bootloader/$TIMESTAMP"

ssh_run "test -d '$BOOT_DIR'"
ssh_run "test -e /dev/mtd/by-name/ospi.tiboot3 && test -e /dev/mtd/by-name/ospi.tispl && test -e /dev/mtd/by-name/ospi.u-boot"
ssh_run "command -v sha256sum >/dev/null"
ssh_run "mkdir -p '$REMOTE_STAGE' '$REMOTE_BACKUP'"

for file in "${FILES[@]}"; do
    scp_to_board "$SRC_DIR/$file" "$REMOTE_STAGE/$file"
done

if [ "$DRY_RUN" -eq 0 ]; then
    REMOTE_STAGE_SHA="$(ssh_capture "sha256sum '$REMOTE_STAGE/tiboot3.bin' '$REMOTE_STAGE/tispl.bin' '$REMOTE_STAGE/u-boot.img'")"
    diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_STAGE_SHA" | awk '{print $1}')
fi

ssh_run "for f in ${FILES[*]}; do if [ -f '$BOOT_DIR/'\"\$f\" ]; then cp '$BOOT_DIR/'\"\$f\" '$REMOTE_BACKUP/'\"\$f\"; fi; done"
ssh_run "for f in ${FILES[*]}; do cp '$REMOTE_STAGE/'\"\$f\" '$BOOT_DIR/'\"\$f\".new && mv '$BOOT_DIR/'\"\$f\".new '$BOOT_DIR/'\"\$f\"; done"

if [ "$DRY_RUN" -eq 0 ]; then
    REMOTE_FINAL_SHA="$(ssh_capture "sha256sum '$BOOT_DIR/tiboot3.bin' '$BOOT_DIR/tispl.bin' '$BOOT_DIR/u-boot.img'")"
    diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_FINAL_SHA" | awk '{print $1}')
    cleanup_remote_stage_on_success "$REMOTE_STAGE"
    cleanup_remote_backup_retention "$BOOT_DIR/backup/bootloader"
fi

ssh_run "sync && ls -lh '$BOOT_DIR'/tiboot3.bin '$BOOT_DIR'/tispl.bin '$BOOT_DIR'/u-boot.img && echo '---' && ls -lh '$REMOTE_BACKUP' || true"

if [ "$REBOOT_AFTER" -eq 1 ]; then
    ssh_run "sync && reboot"
fi

echo "[INFO] Bootloader deploy flow completed."
