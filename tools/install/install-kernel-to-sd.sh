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
MODE=""
REBOOT_AFTER=0
DRY_RUN=0
ARTIFACTS_DIR="$BRINGUP_ROOT/out/kernel/artifacts"
KERNEL_DST="/boot/Image"
DTB_DST="/boot/dtb/ti/k3-am642-sk.dtb"
IMAGE_SRC="$ARTIFACTS_DIR/Image"
DTB_SRC="$ARTIFACTS_DIR/k3-am642-sk.dtb"
LOCAL_SHA_FILE=""
LOCAL_HASH_ONLY_FILE=""
BACKUP_KEEP_COUNT=3

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-kernel-to-sd.sh <board-ip> <all|image-only|dtb-only> [--reboot] [--dry-run]

예:
  ./tools/install/install-kernel-to-sd.sh 192.168.0.110 all
  ./tools/install/install-kernel-to-sd.sh 192.168.0.110 dtb-only --reboot
  ./tools/install/install-kernel-to-sd.sh 192.168.0.110 image-only --dry-run
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

scp_to_board() {
    local src="$1"
    local dst="$2"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN][scp] $src -> root@$BOARD_IP:$dst"
        return 0
    fi

    scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$src" "root@$BOARD_IP:$dst"
}

ssh_capture() {
    local cmd="$1"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[DRY-RUN][ssh-capture] $cmd"
        return 0
    fi

    ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "root@$BOARD_IP" "$cmd"
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

MODE="${2:-}"

if [ -z "$MODE" ]; then
    echo "[ERROR] Mode is required." >&2
    usage >&2
    exit 1
fi

shift 2 || true

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

case "$MODE" in
    all|image-only|dtb-only)
        ;;
    *)
        echo "[ERROR] Unknown mode: $MODE" >&2
        usage >&2
        exit 1
        ;;
esac

LOCAL_SHA_FILE="$(mktemp)"
LOCAL_HASH_ONLY_FILE="$(mktemp)"

case "$MODE" in
    all)
        require_file "$IMAGE_SRC" "kernel Image"
        require_file "$DTB_SRC" "baseline DTB"
        sha256sum "$IMAGE_SRC" "$DTB_SRC" > "$LOCAL_SHA_FILE"
        ;;
    image-only)
        require_file "$IMAGE_SRC" "kernel Image"
        sha256sum "$IMAGE_SRC" > "$LOCAL_SHA_FILE"
        ;;
    dtb-only)
        require_file "$DTB_SRC" "baseline DTB"
        sha256sum "$DTB_SRC" > "$LOCAL_SHA_FILE"
        ;;
esac

awk '{print $1}' "$LOCAL_SHA_FILE" > "$LOCAL_HASH_ONLY_FILE"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="/tmp/ti-bringup-kernel-$TIMESTAMP"
REMOTE_BACKUP_BASE="/boot/backup/kernel/$TIMESTAMP"

ssh_run "test -d '/boot' && test -d '/boot/dtb/ti'"
ssh_run "command -v sha256sum >/dev/null"
ssh_run "mkdir -p '$REMOTE_STAGE' '$REMOTE_BACKUP_BASE/dtb'"

case "$MODE" in
    all|image-only)
        scp_to_board "$IMAGE_SRC" "$REMOTE_STAGE/Image.new"
        if [ "$DRY_RUN" -eq 0 ]; then
            IMAGE_STAGE_SHA="$(ssh_capture "sha256sum '$REMOTE_STAGE/Image.new'")"
            diff -u <(sed -n '1p' "$LOCAL_HASH_ONLY_FILE") <(printf '%s\n' "$IMAGE_STAGE_SHA" | awk '{print $1}')
        fi
        ssh_run "if [ -f '$KERNEL_DST' ]; then cp '$KERNEL_DST' '$REMOTE_BACKUP_BASE/Image'; fi"
        ssh_run "cp '$REMOTE_STAGE/Image.new' '$KERNEL_DST.new' && mv '$KERNEL_DST.new' '$KERNEL_DST'"
        ;;
esac

case "$MODE" in
    all|dtb-only)
        scp_to_board "$DTB_SRC" "$REMOTE_STAGE/k3-am642-sk.dtb.new"
        if [ "$DRY_RUN" -eq 0 ]; then
            DTB_STAGE_SHA="$(ssh_capture "sha256sum '$REMOTE_STAGE/k3-am642-sk.dtb.new'")"
            if [ "$MODE" = "all" ]; then
                diff -u <(sed -n '2p' "$LOCAL_HASH_ONLY_FILE") <(printf '%s\n' "$DTB_STAGE_SHA" | awk '{print $1}')
            else
                diff -u <(sed -n '1p' "$LOCAL_HASH_ONLY_FILE") <(printf '%s\n' "$DTB_STAGE_SHA" | awk '{print $1}')
            fi
        fi
        ssh_run "if [ -f '$DTB_DST' ]; then cp '$DTB_DST' '$REMOTE_BACKUP_BASE/dtb/k3-am642-sk.dtb'; fi"
        ssh_run "cp '$REMOTE_STAGE/k3-am642-sk.dtb.new' '$DTB_DST.new' && mv '$DTB_DST.new' '$DTB_DST'"
        ;;
esac

if [ "$DRY_RUN" -eq 0 ]; then
    case "$MODE" in
        all)
            REMOTE_FINAL_SHA="$(ssh_capture "sha256sum '$KERNEL_DST' '$DTB_DST'")"
            diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_FINAL_SHA" | awk '{print $1}')
            ;;
        image-only)
            REMOTE_FINAL_SHA="$(ssh_capture "sha256sum '$KERNEL_DST'")"
            diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_FINAL_SHA" | awk '{print $1}')
            ;;
        dtb-only)
            REMOTE_FINAL_SHA="$(ssh_capture "sha256sum '$DTB_DST'")"
            diff -u "$LOCAL_HASH_ONLY_FILE" <(printf '%s\n' "$REMOTE_FINAL_SHA" | awk '{print $1}')
            ;;
    esac

    cleanup_remote_stage_on_success "$REMOTE_STAGE"
    cleanup_remote_backup_retention "/boot/backup/kernel"
fi

ssh_run "sync && if [ -f '$KERNEL_DST' ]; then ls -lh '$KERNEL_DST'; fi && if [ -f '$DTB_DST' ]; then ls -lh '$DTB_DST'; fi && echo '---' && ls -R '$REMOTE_BACKUP_BASE' || true"

if [ "$REBOOT_AFTER" -eq 1 ]; then
    ssh_run "sync && reboot"
fi

echo "[INFO] Kernel/DTB deploy flow completed."
