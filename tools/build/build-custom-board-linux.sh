#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"
SYNC_HELPER="$BRINGUP_ROOT/tools/prepare/sync-custom-board-dts-set-to-workspace.sh"
VERIFY_SCRIPT="$BRINGUP_ROOT/tools/prepare/verify-workspace-state.sh"

ACTION="${1:-all}"
BOARD="cpu_brd_v03_pba_260511"
PURPOSE="bringup-default"

BUILD_BASE="$BRINGUP_ROOT/out/kernel-custom-board/$BOARD/$PURPOSE"
ARTIFACTS="$BUILD_BASE/artifacts"
MODULES_OUT="$BUILD_BASE/modules"
LOG_DIR="$BUILD_BASE/logs"
DTB_NAME="k3-am6412-cpu-brd-v03-pba.dtb"
DTB_SOURCE_DIR_REL="arch/arm64/boot/dts/ti"
IMAGE_REL="arch/arm64/boot/Image"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-custom-board-linux.sh defconfig
  ./tools/build/build-custom-board-linux.sh image
  ./tools/build/build-custom-board-linux.sh dtbs
  ./tools/build/build-custom-board-linux.sh modules
  ./tools/build/build-custom-board-linux.sh all
  ./tools/build/build-custom-board-linux.sh artifacts
EOF
}

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

sanitize_standalone_env() {
    local contamination_detected=0
    local var_name

    for var_name in \
        OECORE_NATIVE_SYSROOT OECORE_TARGET_SYSROOT SDKTARGETSYSROOT CONFIG_SITE \
        CC CXX CPP LD AR AS NM STRIP OBJCOPY OBJDUMP RANLIB READELF \
        CFLAGS CPPFLAGS CXXFLAGS LDFLAGS PKG_CONFIG_PATH PKG_CONFIG_SYSROOT_DIR \
        PYTHONHOME PYTHONPATH
    do
        if [ -n "${!var_name:-}" ]; then
            contamination_detected=1
            unset "$var_name"
        fi
    done

    if [ "$contamination_detected" -eq 1 ]; then
        echo "[WARN] Cleared inherited SDK/host environment variables for standalone kernel build." >&2
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

require_file() {
    local path="$1"
    local label="$2"

    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

ensure_inputs() {
    require_dir "$KERNEL_SRC" "kernel workspace"
    require_dir "$KERNEL_SRC/.git" "kernel workspace git repository"
    require_dir "$KERNEL_SRC/$DTB_SOURCE_DIR_REL" "kernel DTB source directory"
    require_file "$SYNC_HELPER" "custom board DTS sync helper"

    if [ "$KERNEL_SRC" = "$KERNEL_SDK_SRC" ]; then
        echo "[ERROR] Refusing to build from SDK reference source: $KERNEL_SRC" >&2
        exit 1
    fi

    case "$KERNEL_SRC" in
        "$WORKSPACE_ROOT"/*) ;;
        *)
            echo "[ERROR] Refusing to build outside workspace/: $KERNEL_SRC" >&2
            exit 1
            ;;
    esac

    sanitize_standalone_env
    mkdir -p "$ARTIFACTS" "$MODULES_OUT" "$LOG_DIR"
}

prepare_workspace_projection() {
    if [ -x "$VERIFY_SCRIPT" ]; then
        ALLOW_DIRTY_WORKSPACE=1 "$VERIFY_SCRIPT"
    fi

    "$SYNC_HELPER" linux "$BOARD" "$PURPOSE"
}

run_defconfig() {
    echo "[INFO] Custom board Linux build currently follows the repo baseline policy: make defconfig."

    make -C "$KERNEL_SRC" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        defconfig | tee "$LOG_DIR/defconfig.log"
}

build_image() {
    make -C "$KERNEL_SRC" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        -j"$(nproc)" \
        Image | tee "$LOG_DIR/image.log"
}

build_dtbs() {
    make -C "$KERNEL_SRC" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        -j"$(nproc)" \
        dtbs | tee "$LOG_DIR/dtbs.log"
}

build_modules() {
    make -C "$KERNEL_SRC" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        -j"$(nproc)" \
        modules | tee "$LOG_DIR/modules.log"

    rm -rf "$MODULES_OUT"
    mkdir -p "$MODULES_OUT"

    make -C "$KERNEL_SRC" \
        ARCH=arm64 \
        CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        INSTALL_MOD_PATH="$MODULES_OUT" \
        modules_install | tee "$LOG_DIR/modules-install.log"
}

collect_artifacts() {
    local image_path="$KERNEL_SRC/$IMAGE_REL"
    local dtb_path="$KERNEL_SRC/$DTB_SOURCE_DIR_REL/$DTB_NAME"

    require_file "$image_path" "kernel Image"
    require_file "$dtb_path" "custom board DTB"

    cp "$image_path" "$ARTIFACTS/Image"
    cp "$dtb_path" "$ARTIFACTS/$DTB_NAME"
}

generate_manifest() {
    local manifest="$ARTIFACTS/build-manifest.txt"
    local branch
    local kernel_release

    branch="$(git -C "$KERNEL_SRC" rev-parse --abbrev-ref HEAD)"
    kernel_release="$(make -s -C "$KERNEL_SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE_AARCH64" kernelrelease)"

    {
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'SDK_VERSION: %s\n' "$SDK_VERSION"
        printf 'BOARD: %s\n' "$BOARD"
        printf 'PURPOSE: %s\n' "$PURPOSE"
        printf 'KERNEL_SRC: %s\n' "$KERNEL_SRC"
        printf 'KERNEL_HEAD: %s\n' "$(git -C "$KERNEL_SRC" rev-parse HEAD)"
        printf 'KERNEL_BRANCH: %s\n' "$branch"
        printf 'KERNEL_RELEASE: %s\n' "$kernel_release"
        printf 'DTS_SET: %s\n' "$BRINGUP_ROOT/bsp/linux/dts/custom-board/$BOARD/sets/$PURPOSE"
        printf 'SYNC_HELPER: %s\n' "$SYNC_HELPER linux $BOARD $PURPOSE"
        printf 'BUILD_COMMAND: %s\n' "./tools/build/build-custom-board-linux.sh $ACTION"
        printf '\n[artifact sizes]\n'
        stat -c '%n %s bytes' "$ARTIFACTS/Image" "$ARTIFACTS/$DTB_NAME"
        printf '\n[sha256]\n'
        sha256sum "$ARTIFACTS/Image" "$ARTIFACTS/$DTB_NAME"
    } > "$manifest"
}

show_artifacts() {
    ls -lh "$ARTIFACTS/Image" "$ARTIFACTS/$DTB_NAME"
    sha256sum "$ARTIFACTS/Image" "$ARTIFACTS/$DTB_NAME"
}

ensure_inputs
prepare_workspace_projection

case "$ACTION" in
    defconfig)
        run_defconfig
        ;;
    image)
        run_defconfig
        build_image
        ;;
    dtbs)
        run_defconfig
        build_dtbs
        ;;
    modules)
        run_defconfig
        build_modules
        ;;
    all)
        run_defconfig
        build_image
        build_dtbs
        build_modules
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    artifacts)
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
