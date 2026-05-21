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

VERIFY_SCRIPT="$BRINGUP_ROOT/tools/prepare/verify-workspace-state.sh"

if [ ! -x "$VERIFY_SCRIPT" ]; then
    echo "[ERROR] Verification script is missing or not executable: $VERIFY_SCRIPT" >&2
    exit 1
fi

"$VERIFY_SCRIPT"

ACTION="${1:-all}"

BUILD_BASE="$BRINGUP_ROOT/out/kernel"
ARTIFACTS="$BUILD_BASE/artifacts"
MODULES_OUT="$BUILD_BASE/modules"
LOG_DIR="$BUILD_BASE/logs"
DTB_SOURCE_DIR="$KERNEL_SRC/arch/arm64/boot/dts/ti"
IMAGE_PATH="$KERNEL_SRC/arch/arm64/boot/Image"

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

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-kernel.sh defconfig
  ./tools/build/build-kernel.sh image
  ./tools/build/build-kernel.sh dtbs
  ./tools/build/build-kernel.sh modules
  ./tools/build/build-kernel.sh all
  ./tools/build/build-kernel.sh artifacts
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

require_file() {
    local path="$1"
    local label="$2"

    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

require_clean_workspace() {
    local dirty
    dirty="$(git -C "$KERNEL_SRC" status --short)"

    if [ -n "$dirty" ]; then
        echo "[ERROR] Kernel workspace is dirty. Stop before building." >&2
        printf '%s\n' "$dirty" >&2
        exit 1
    fi
}

ensure_inputs() {
    require_dir "$KERNEL_SRC" "kernel workspace"
    require_dir "$KERNEL_SRC/.git" "kernel workspace git repository"
    require_dir "$DTB_SOURCE_DIR" "kernel DTB source directory"

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

    require_clean_workspace
    sanitize_standalone_env
    mkdir -p "$ARTIFACTS" "$MODULES_OUT" "$LOG_DIR"
}

list_dtb_candidates() {
    find "$DTB_SOURCE_DIR" -maxdepth 1 -name 'k3-am64*.dts' -print | sort
}

run_defconfig() {
    echo "[INFO] Temporary defconfig policy: using make defconfig."
    echo "[INFO] Open question: confirm exact TI SDK defconfig/config fragment for Processor SDK Linux 12 AM64x."

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
    local dtb_count

    require_file "$IMAGE_PATH" "kernel Image"

    rm -f "$ARTIFACTS/Image"
    find "$ARTIFACTS" -maxdepth 1 -name 'k3-am64*.dtb' -type f -delete
    cp "$IMAGE_PATH" "$ARTIFACTS/Image"

    dtb_count="$(find "$DTB_SOURCE_DIR" -maxdepth 1 -name 'k3-am64*.dtb' -type f | wc -l)"
    if [ "$dtb_count" -eq 0 ]; then
        echo "[ERROR] No k3-am64*.dtb artifacts found under $DTB_SOURCE_DIR" >&2
        exit 1
    fi

    find "$DTB_SOURCE_DIR" -maxdepth 1 -name 'k3-am64*.dtb' -type f -exec cp {} "$ARTIFACTS" \;

    dtb_count="$(find "$ARTIFACTS" -maxdepth 1 -name 'k3-am64*.dtb' | wc -l)"
    if [ "$dtb_count" -eq 0 ]; then
        echo "[ERROR] DTB artifact copy failed for $DTB_SOURCE_DIR" >&2
        exit 1
    fi

    list_dtb_candidates > "$ARTIFACTS/dtb-candidates.txt"
}

generate_manifest() {
    local manifest
    local branch
    local kernel_release

    manifest="$ARTIFACTS/build-manifest.txt"
    branch="$(git -C "$KERNEL_SRC" rev-parse --abbrev-ref HEAD)"
    kernel_release="$(make -s -C "$KERNEL_SRC" ARCH=arm64 CROSS_COMPILE="$CROSS_COMPILE_AARCH64" kernelrelease)"

    {
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'SDK_VERSION: %s\n' "$SDK_VERSION"
        printf 'KERNEL_SRC: %s\n' "$KERNEL_SRC"
        printf 'KERNEL_HEAD: %s\n' "$(git -C "$KERNEL_SRC" rev-parse HEAD)"
        printf 'KERNEL_BRANCH: %s\n' "$branch"
        printf 'KERNEL_RELEASE: %s\n' "$kernel_release"
        printf 'ARTIFACTS_DIR: %s\n' "$ARTIFACTS"
        printf 'MODULES_OUT: %s\n' "$MODULES_OUT"
        printf 'BUILD_COMMAND: %s\n' "./tools/build/build-kernel.sh $ACTION"
        printf 'DEFCONFIG_POLICY: %s\n' 'Temporary: make defconfig is used. Open question: confirm exact TI SDK defconfig/config fragment used by Processor SDK Linux 12 AM64x.'
        printf '\n[artifact sizes]\n'
        find "$ARTIFACTS" -maxdepth 1 \( -name 'Image' -o -name 'k3-am64*.dtb' \) -type f -print0 | sort -z | xargs -0 stat -c '%n %s bytes'
        printf '\n[sha256]\n'
        find "$ARTIFACTS" -maxdepth 1 \( -name 'Image' -o -name 'k3-am64*.dtb' \) -type f -print0 | sort -z | xargs -0 sha256sum
    } > "$manifest"
}

show_artifacts() {
    ls -lh "$ARTIFACTS/Image"
    find "$ARTIFACTS" -maxdepth 1 -name 'k3-am64*.dtb' -type f | sort | xargs ls -lh
}

case "$ACTION" in
    defconfig)
        ensure_inputs
        run_defconfig
        ;;
    image)
        ensure_inputs
        build_image
        ;;
    dtbs)
        ensure_inputs
        build_dtbs
        ;;
    modules)
        ensure_inputs
        build_modules
        ;;
    all)
        ensure_inputs
        run_defconfig
        build_image
        build_dtbs
        build_modules
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    artifacts)
        ensure_inputs
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
