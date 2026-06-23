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
MODE="${2:-all}"
DRY_RUN=0

BOARD="cpu_brd_v03_pba_260511"
PURPOSE="bringup-default"

UBOOT_ARTIFACTS="$BRINGUP_ROOT/out/u-boot-custom-board/$BOARD/$PURPOSE/artifacts"
KERNEL_ARTIFACTS="$BRINGUP_ROOT/out/kernel-custom-board/$BOARD/$PURPOSE/artifacts"
MODULES_BASE="$BRINGUP_ROOT/out/kernel-custom-board/$BOARD/$PURPOSE/modules/lib/modules"

BOOT_FILES=(tiboot3.bin tispl.bin u-boot.img)

BOOT0_DEVICE="/dev/mmcblk0boot0"
BOOT0_FORCE_RO="/sys/class/block/mmcblk0boot0/force_ro"
BOOT_MOUNT="/run/media/boot-mmcblk0p1"
REMOTE_BOOT_DIR="/boot"
REMOTE_DTB_DIR="/boot/dtb/ti"
REMOTE_IMAGE="$REMOTE_BOOT_DIR/Image"
REMOTE_CUSTOM_DTB="$REMOTE_DTB_DIR/k3-am6412-cpu-brd-v03-pba.dtb"
REMOTE_COMPAT_DTB="$REMOTE_DTB_DIR/k3-am642-sk.dtb"

LOCAL_IMAGE="$KERNEL_ARTIFACTS/Image"
LOCAL_DTB="$KERNEL_ARTIFACTS/k3-am6412-cpu-brd-v03-pba.dtb"

LOCAL_MODULES_DIR=""
KERNEL_RELEASE=""

usage() {
    cat <<'EOF'
Usage:
  ./tools/install/install-custom-board-emmc.sh <board-ip> [all|bootloader|linux|modules] [--dry-run]

Examples:
  ./tools/install/install-custom-board-emmc.sh 192.168.0.154
  ./tools/install/install-custom-board-emmc.sh 192.168.0.154 bootloader
  ./tools/install/install-custom-board-emmc.sh 192.168.0.154 linux --dry-run
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

require_dir() {
    local path="$1"
    local label="$2"

    if [ ! -d "$path" ]; then
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

detect_local_modules_dir() {
    local -a candidates=()
    local candidate

    require_dir "$MODULES_BASE" "custom board modules base"

    while IFS= read -r candidate; do
        candidates+=("$candidate")
    done < <(python3 - <<'PY' "$MODULES_BASE"
import os, sys
base = sys.argv[1]
for name in sorted(os.listdir(base)):
    path = os.path.join(base, name)
    if os.path.isdir(path):
        print(path)
PY
)

    if [ "${#candidates[@]}" -eq 0 ]; then
        echo "[ERROR] No installed module release directory found under $MODULES_BASE" >&2
        exit 1
    fi

    if [ "${#candidates[@]}" -ne 1 ]; then
        printf '[ERROR] Expected exactly one module release directory under %s, found:\n' "$MODULES_BASE" >&2
        printf '  %s\n' "${candidates[@]}" >&2
        exit 1
    fi

    LOCAL_MODULES_DIR="${candidates[0]}"
    KERNEL_RELEASE="$(basename "$LOCAL_MODULES_DIR")"
}

if [ -z "$BOARD_IP" ]; then
    usage >&2
    exit 1
fi

shift || true

if [ "$#" -gt 0 ]; then
    case "$1" in
        all|bootloader|linux|modules)
            MODE="$1"
            shift
            ;;
    esac
fi

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
            echo "[ERROR] Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

case "$MODE" in
    all|bootloader|linux|modules)
        ;;
    *)
        echo "[ERROR] Unknown mode: $MODE" >&2
        usage >&2
        exit 1
        ;;
esac

for file in "${BOOT_FILES[@]}"; do
    require_file "$UBOOT_ARTIFACTS/$file" "$file artifact"
done
require_file "$LOCAL_IMAGE" "custom board kernel Image"
require_file "$LOCAL_DTB" "custom board DTB"
detect_local_modules_dir

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="/tmp/ti-bringup-custom-emmc-$TIMESTAMP"
REMOTE_BACKUP_BASE="/root/ti-bringup-backup/$TIMESTAMP"
REMOTE_MODULES_DIR="/lib/modules/$KERNEL_RELEASE"

ssh_run "test -e '$BOOT0_DEVICE' && test -e '$BOOT0_FORCE_RO' && test -d '$BOOT_MOUNT' && test -d '$REMOTE_DTB_DIR' && command -v dd >/dev/null && command -v sha256sum >/dev/null && command -v tar >/dev/null"
ssh_run "mkdir -p '$REMOTE_STAGE' '$REMOTE_BACKUP_BASE/bootloader-fat' '$REMOTE_BACKUP_BASE/boot' '$REMOTE_BACKUP_BASE/modules'"

deploy_bootloader() {
    local file
    local size
    local sector
    local readback_count
    local stage_hash

    for file in "${BOOT_FILES[@]}"; do
        scp_to_board "$UBOOT_ARTIFACTS/$file" "$REMOTE_STAGE/$file"
        if [ "$DRY_RUN" -eq 0 ]; then
            stage_hash="$(ssh_capture "sha256sum '$REMOTE_STAGE/$file'")"
            diff -u <(sha256sum "$UBOOT_ARTIFACTS/$file" | awk '{print $1}') <(printf '%s\n' "$stage_hash" | awk '{print $1}')
        fi
    done

    ssh_run "for f in ${BOOT_FILES[*]}; do if [ -f '$BOOT_MOUNT/'\"\$f\" ]; then cp '$BOOT_MOUNT/'\"\$f\" '$REMOTE_BACKUP_BASE/bootloader-fat/'\"\$f\"; fi; done"
    ssh_run "echo 0 > '$BOOT0_FORCE_RO' && dd if='$BOOT0_DEVICE' of='$REMOTE_BACKUP_BASE/boot0-before.bin' bs=512 count=8192 && sync"

    for file in "${BOOT_FILES[@]}"; do
        case "$file" in
            tiboot3.bin) sector=$((0x0)) ;;
            tispl.bin) sector=$((0x400)) ;;
            u-boot.img) sector=$((0x1400)) ;;
        esac

        ssh_run "dd if='$REMOTE_STAGE/$file' of='$BOOT0_DEVICE' bs=512 seek=$sector conv=fsync,notrunc"
        ssh_run "cp '$REMOTE_STAGE/$file' '$BOOT_MOUNT/$file.new' && mv '$BOOT_MOUNT/$file.new' '$BOOT_MOUNT/$file'"

        if [ "$DRY_RUN" -eq 0 ]; then
            size="$(stat -c '%s' "$UBOOT_ARTIFACTS/$file")"
            readback_count=$(((size + 511) / 512))
            ssh_run "dd if='$BOOT0_DEVICE' of='$REMOTE_STAGE/$file.readback' bs=512 skip=$sector count=$readback_count"
            ssh_run "cmp -n $size '$REMOTE_STAGE/$file' '$REMOTE_STAGE/$file.readback'"
            diff -u <(sha256sum "$UBOOT_ARTIFACTS/$file" | awk '{print $1}') <(ssh_capture "sha256sum '$BOOT_MOUNT/$file'" | awk '{print $1}')
        fi
    done

    ssh_run "echo 1 > '$BOOT0_FORCE_RO' && sync"
}

deploy_linux_assets() {
    local image_hash
    local dtb_hash

    scp_to_board "$LOCAL_IMAGE" "$REMOTE_STAGE/Image"
    scp_to_board "$LOCAL_DTB" "$REMOTE_STAGE/k3-am6412-cpu-brd-v03-pba.dtb"

    if [ "$DRY_RUN" -eq 0 ]; then
        image_hash="$(ssh_capture "sha256sum '$REMOTE_STAGE/Image'")"
        dtb_hash="$(ssh_capture "sha256sum '$REMOTE_STAGE/k3-am6412-cpu-brd-v03-pba.dtb'")"
        diff -u <(sha256sum "$LOCAL_IMAGE" | awk '{print $1}') <(printf '%s\n' "$image_hash" | awk '{print $1}')
        diff -u <(sha256sum "$LOCAL_DTB" | awk '{print $1}') <(printf '%s\n' "$dtb_hash" | awk '{print $1}')
    fi

    ssh_run "if [ -f '$REMOTE_IMAGE' ]; then cp '$REMOTE_IMAGE' '$REMOTE_BACKUP_BASE/boot/Image'; fi"
    ssh_run "if [ -f '$REMOTE_COMPAT_DTB' ]; then cp '$REMOTE_COMPAT_DTB' '$REMOTE_BACKUP_BASE/boot/k3-am642-sk.dtb'; fi"
    ssh_run "if [ -f '$REMOTE_CUSTOM_DTB' ]; then cp '$REMOTE_CUSTOM_DTB' '$REMOTE_BACKUP_BASE/boot/k3-am6412-cpu-brd-v03-pba.dtb'; fi"

    ssh_run "cp '$REMOTE_STAGE/Image' '$REMOTE_IMAGE.new' && mv '$REMOTE_IMAGE.new' '$REMOTE_IMAGE'"
    ssh_run "cp '$REMOTE_STAGE/k3-am6412-cpu-brd-v03-pba.dtb' '$REMOTE_CUSTOM_DTB.new' && mv '$REMOTE_CUSTOM_DTB.new' '$REMOTE_CUSTOM_DTB'"
    ssh_run "cp '$REMOTE_STAGE/k3-am6412-cpu-brd-v03-pba.dtb' '$REMOTE_COMPAT_DTB.new' && mv '$REMOTE_COMPAT_DTB.new' '$REMOTE_COMPAT_DTB'"

    if [ "$DRY_RUN" -eq 0 ]; then
        diff -u <(sha256sum "$LOCAL_IMAGE" | awk '{print $1}') <(ssh_capture "sha256sum '$REMOTE_IMAGE'" | awk '{print $1}')
        diff -u <(sha256sum "$LOCAL_DTB" | awk '{print $1}') <(ssh_capture "sha256sum '$REMOTE_CUSTOM_DTB'" | awk '{print $1}')
        diff -u <(sha256sum "$LOCAL_DTB" | awk '{print $1}') <(ssh_capture "sha256sum '$REMOTE_COMPAT_DTB'" | awk '{print $1}')
    fi
}

deploy_modules() {
    local local_tar
    local local_tar_hash
    local remote_tar_hash

    local_tar="$(mktemp --suffix=.tar)"

    tar -C "$MODULES_BASE" -cf "$local_tar" "$KERNEL_RELEASE"
    scp_to_board "$local_tar" "$REMOTE_STAGE/$KERNEL_RELEASE.tar"

    if [ "$DRY_RUN" -eq 0 ]; then
        local_tar_hash="$(sha256sum "$local_tar" | awk '{print $1}')"
        remote_tar_hash="$(ssh_capture "sha256sum '$REMOTE_STAGE/$KERNEL_RELEASE.tar'")"
        diff -u <(printf '%s\n' "$local_tar_hash") <(printf '%s\n' "$remote_tar_hash" | awk '{print $1}')
    fi

    ssh_run "rm -rf '$REMOTE_STAGE/extracted' '$REMOTE_MODULES_DIR.new' && mkdir -p '$REMOTE_STAGE/extracted' && tar -xf '$REMOTE_STAGE/$KERNEL_RELEASE.tar' -C '$REMOTE_STAGE/extracted'"
    ssh_run "test -d '$REMOTE_STAGE/extracted/$KERNEL_RELEASE'"
    ssh_run "if [ -d '$REMOTE_MODULES_DIR' ]; then cp -a '$REMOTE_MODULES_DIR' '$REMOTE_BACKUP_BASE/modules/$KERNEL_RELEASE'; fi"
    ssh_run "cp -a '$REMOTE_STAGE/extracted/$KERNEL_RELEASE' '$REMOTE_MODULES_DIR.new' && rm -rf '$REMOTE_MODULES_DIR' && mv '$REMOTE_MODULES_DIR.new' '$REMOTE_MODULES_DIR'"
    ssh_run "if command -v depmod >/dev/null; then depmod -a '$KERNEL_RELEASE'; fi"
    ssh_run "sync"

    rm -f "$local_tar"
}

case "$MODE" in
    all)
        deploy_bootloader
        deploy_linux_assets
        deploy_modules
        ;;
    bootloader)
        deploy_bootloader
        ;;
    linux)
        deploy_linux_assets
        ;;
    modules)
        deploy_modules
        ;;
esac

ssh_run "sync && ls -lh '$REMOTE_IMAGE' '$REMOTE_COMPAT_DTB' '$REMOTE_CUSTOM_DTB' && echo '--- boot0 ---' && ls -lh '$BOOT0_DEVICE' && echo '--- boot FAT ---' && ls -lh '$BOOT_MOUNT'/tiboot3.bin '$BOOT_MOUNT'/tispl.bin '$BOOT_MOUNT'/u-boot.img && echo '--- modules ---' && ls -ld '$REMOTE_MODULES_DIR' && echo '--- backup ---' && ls -R '$REMOTE_BACKUP_BASE'"

echo "[INFO] Custom board eMMC deploy flow completed: mode=$MODE"
