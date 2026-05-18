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
DRY_RUN=0
VERIFY_POST_DEPLOY=0
MODULES_BASE="$BRINGUP_ROOT/out/kernel/modules/lib/modules"
KERNEL_RELEASE=""
LOCAL_MODULES_DIR=""
LOCAL_MODULES_TAR=""
LOCAL_TAR_SHA_FILE=""
LOCAL_REQUIRED_MODULE_SHA_FILE=""
BACKUP_KEEP_COUNT=3

REQUIRED_MODULE_PATHS=(
    "kernel/drivers/remoteproc/ti_k3_r5_remoteproc.ko"
    "kernel/drivers/remoteproc/ti_k3_m4_remoteproc.ko"
    "kernel/drivers/rpmsg/rpmsg_char.ko"
    "kernel/drivers/rpmsg/rpmsg_ctrl.ko"
)

usage() {
    cat <<'EOF'
사용법:
  ./tools/install/install-kernel-modules-to-sd.sh <board-ip> <deploy|promote-golden|restore-golden> [--dry-run] [--verify-post-deploy]

예:
  ./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy
  ./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 deploy --verify-post-deploy
  ./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 promote-golden
  ./tools/install/install-kernel-modules-to-sd.sh 192.168.0.110 restore-golden
EOF
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

cleanup_local_tempfiles() {
    rm -f "${LOCAL_MODULES_TAR:-}" "${LOCAL_TAR_SHA_FILE:-}" "${LOCAL_REQUIRED_MODULE_SHA_FILE:-}"
}

collect_remote_required_module_hashes() {
    local rel_path

    for rel_path in "${REQUIRED_MODULE_PATHS[@]}"; do
        ssh_capture "sha256sum '$REMOTE_MODULES_DIR/$rel_path'"
    done
}

cleanup_remote_backup_retention() {
    local backup_parent="$1"

    ssh_run "if [ -d '$backup_parent' ]; then ls -1dt '$backup_parent'/* 2>/dev/null | tail -n +$((BACKUP_KEEP_COUNT + 1)) | xargs -r rm -rf; fi"
}

cleanup_remote_stage_on_success() {
    local stage_dir="$1"

    ssh_run "rm -rf '$stage_dir'"
}

detect_local_modules_dir() {
    local -a candidates=()
    local candidate

    require_dir "$MODULES_BASE" "local kernel modules base"

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

verify_local_required_modules() {
    local rel_path

    for rel_path in "${REQUIRED_MODULE_PATHS[@]}"; do
        if [ ! -f "$LOCAL_MODULES_DIR/$rel_path" ]; then
            echo "[ERROR] Missing required module artifact: $LOCAL_MODULES_DIR/$rel_path" >&2
            exit 1
        fi
    done
}

prepare_local_archive() {
    LOCAL_MODULES_TAR="$(mktemp --suffix=.tar)"
    LOCAL_TAR_SHA_FILE="$(mktemp)"
    LOCAL_REQUIRED_MODULE_SHA_FILE="$(mktemp)"

    tar -C "$MODULES_BASE" -cf "$LOCAL_MODULES_TAR" "$KERNEL_RELEASE"
    sha256sum "$LOCAL_MODULES_TAR" > "$LOCAL_TAR_SHA_FILE"

    python3 - <<'PY' "$LOCAL_MODULES_DIR" "$LOCAL_REQUIRED_MODULE_SHA_FILE" "${REQUIRED_MODULE_PATHS[@]}"
import hashlib, os, sys
base = sys.argv[1]
out_path = sys.argv[2]
required = sys.argv[3:]
with open(out_path, 'w', encoding='utf-8') as out:
    for rel in required:
        path = os.path.join(base, rel)
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        out.write(h.hexdigest() + '\n')
PY
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
        --dry-run)
            DRY_RUN=1
            ;;
        --verify-post-deploy)
            VERIFY_POST_DEPLOY=1
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
    deploy|promote-golden|restore-golden)
        ;;
    *)
        echo "[ERROR] Unknown mode: $MODE" >&2
        usage >&2
        exit 1
        ;;
esac

detect_local_modules_dir

REMOTE_MODULES_BASE="/lib/modules"
REMOTE_MODULES_DIR="$REMOTE_MODULES_BASE/$KERNEL_RELEASE"
REMOTE_GOLDEN_BASE="$REMOTE_MODULES_BASE/golden"
REMOTE_GOLDEN_DIR="$REMOTE_GOLDEN_BASE/$KERNEL_RELEASE"
REMOTE_BACKUP_PARENT="$REMOTE_MODULES_BASE/backup/$KERNEL_RELEASE"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REMOTE_STAGE="/tmp/ti-bringup-modules-$TIMESTAMP"
REMOTE_BACKUP_DIR="$REMOTE_BACKUP_PARENT/$TIMESTAMP"

ssh_run "test -d '$REMOTE_MODULES_BASE' && command -v sha256sum >/dev/null && command -v tar >/dev/null"

case "$MODE" in
    deploy)
        verify_local_required_modules
        prepare_local_archive

        ssh_run "mkdir -p '$REMOTE_STAGE' '$REMOTE_BACKUP_PARENT'"
        scp_to_board "$LOCAL_MODULES_TAR" "$REMOTE_STAGE/$KERNEL_RELEASE.tar"

        if [ "$DRY_RUN" -eq 0 ]; then
            REMOTE_TAR_SHA="$(ssh_capture "sha256sum '$REMOTE_STAGE/$KERNEL_RELEASE.tar'")"
            diff -u <(awk '{print $1}' "$LOCAL_TAR_SHA_FILE") <(printf '%s\n' "$REMOTE_TAR_SHA" | awk '{print $1}')
        fi

        ssh_run "rm -rf '$REMOTE_STAGE/extracted' '$REMOTE_MODULES_DIR.new' && mkdir -p '$REMOTE_STAGE/extracted' && tar -xf '$REMOTE_STAGE/$KERNEL_RELEASE.tar' -C '$REMOTE_STAGE/extracted'"
        ssh_run "test -d '$REMOTE_STAGE/extracted/$KERNEL_RELEASE'"

        for rel_path in "${REQUIRED_MODULE_PATHS[@]}"; do
            ssh_run "test -f '$REMOTE_STAGE/extracted/$KERNEL_RELEASE/$rel_path'"
        done

        ssh_run "if [ -d '$REMOTE_MODULES_DIR' ]; then cp -a '$REMOTE_MODULES_DIR' '$REMOTE_BACKUP_DIR'; fi"
        ssh_run "cp -a '$REMOTE_STAGE/extracted/$KERNEL_RELEASE' '$REMOTE_MODULES_DIR.new' && rm -rf '$REMOTE_MODULES_DIR' && mv '$REMOTE_MODULES_DIR.new' '$REMOTE_MODULES_DIR'"
        ssh_run "if command -v depmod >/dev/null; then depmod -a '$KERNEL_RELEASE'; fi"

        if [ "$DRY_RUN" -eq 0 ]; then
            REMOTE_REQUIRED_SHA="$(collect_remote_required_module_hashes)"
            diff -u "$LOCAL_REQUIRED_MODULE_SHA_FILE" <(printf '%s\n' "$REMOTE_REQUIRED_SHA" | awk '{print $1}')
            cleanup_remote_stage_on_success "$REMOTE_STAGE"
            cleanup_remote_backup_retention "$REMOTE_BACKUP_PARENT"
        fi
        ;;
    promote-golden)
        ssh_run "test -d '$REMOTE_MODULES_DIR' && mkdir -p '$REMOTE_GOLDEN_BASE' && rm -rf '$REMOTE_GOLDEN_DIR.new' && cp -a '$REMOTE_MODULES_DIR' '$REMOTE_GOLDEN_DIR.new' && rm -rf '$REMOTE_GOLDEN_DIR' && mv '$REMOTE_GOLDEN_DIR.new' '$REMOTE_GOLDEN_DIR'"
        ;;
    restore-golden)
        ssh_run "test -d '$REMOTE_GOLDEN_DIR' && mkdir -p '$REMOTE_BACKUP_PARENT'"
        ssh_run "if [ -d '$REMOTE_MODULES_DIR' ]; then cp -a '$REMOTE_MODULES_DIR' '$REMOTE_BACKUP_DIR'; fi"
        ssh_run "rm -rf '$REMOTE_MODULES_DIR.new' && cp -a '$REMOTE_GOLDEN_DIR' '$REMOTE_MODULES_DIR.new' && rm -rf '$REMOTE_MODULES_DIR' && mv '$REMOTE_MODULES_DIR.new' '$REMOTE_MODULES_DIR'"
        ssh_run "if command -v depmod >/dev/null; then depmod -a '$KERNEL_RELEASE'; fi"

        if [ "$DRY_RUN" -eq 0 ]; then
            cleanup_remote_backup_retention "$REMOTE_BACKUP_PARENT"
        fi
        ;;
esac

ssh_run "sync && if [ -d '$REMOTE_MODULES_DIR' ]; then ls -ld '$REMOTE_MODULES_DIR'; fi && if [ -d '$REMOTE_GOLDEN_DIR' ]; then ls -ld '$REMOTE_GOLDEN_DIR'; fi && if [ -d '$REMOTE_BACKUP_DIR' ]; then ls -ld '$REMOTE_BACKUP_DIR'; fi"

if [ "$VERIFY_POST_DEPLOY" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    "$SCRIPT_DIR/verify-kernel-modules-postdeploy.sh" "$BOARD_IP" "$KERNEL_RELEASE"
fi

echo "[INFO] Kernel modules deploy flow completed for $KERNEL_RELEASE."
