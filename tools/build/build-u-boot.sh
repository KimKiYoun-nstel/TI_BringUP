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

if [ -n "${UBOOT_SRC_OVERRIDE:-}" ]; then
    UBOOT_SRC="$UBOOT_SRC_OVERRIDE"
fi

VERIFY_SCRIPT="$BRINGUP_ROOT/tools/prepare/verify-workspace-state.sh"

if [ ! -x "$VERIFY_SCRIPT" ]; then
    echo "[ERROR] Verification script is missing or not executable: $VERIFY_SCRIPT" >&2
    exit 1
fi

ACTION="${1:-all}"

BUILD_BASE="${UBOOT_BUILD_BASE:-$BRINGUP_ROOT/out/u-boot}"
R5_OUT="$BUILD_BASE/r5"
A53_OUT="$BUILD_BASE/a53"
ARTIFACTS="$BUILD_BASE/artifacts"
LOG_DIR="$BUILD_BASE/logs"
PREBUILT_DIR="$PREBUILT_IMAGES/am64xx-evm"
BL31_INPUT="${BL31_BIN:-$PREBUILT_DIR/bl31.bin}"
TEE_INPUT="${TEE_BIN:-$PREBUILT_DIR/bl32.bin}"
UBOOT_WATCHDOG_CONFIG_FRAGMENT="$BRINGUP_ROOT/bsp/u-boot/configs/am64x-watchdog.config"

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
        echo "[WARN] Cleared inherited SDK/host environment variables for standalone U-Boot build." >&2
    fi
}

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-u-boot.sh clean
  ./tools/build/build-u-boot.sh r5
  ./tools/build/build-u-boot.sh a53
  ./tools/build/build-u-boot.sh a53-watchdog
  ./tools/build/build-u-boot.sh all
  ./tools/build/build-u-boot.sh all-watchdog
  ./tools/build/build-u-boot.sh artifacts
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

apply_a53_watchdog_config() {
    require_file "$UBOOT_WATCHDOG_CONFIG_FRAGMENT" "U-Boot watchdog config fragment"

    "$UBOOT_SRC/scripts/config" --file "$A53_OUT/.config" \
        -e CMD_WDT \
        -e WDT \
        -e WDT_K3_RTI \
        -d WATCHDOG_AUTOSTART
}

require_clean_workspace() {
    local dirty
    dirty="$(git -C "$UBOOT_SRC" status --short)"

    if [ -n "$dirty" ]; then
        echo "[ERROR] U-Boot workspace is dirty. Stop before building." >&2
        printf '%s\n' "$dirty" >&2
        exit 1
    fi
}

find_libgcc() {
    LIBGCC_FILE="$(find "$LINUX_DEVKIT" -name "libgcc.a" -print 2>/dev/null | grep -E 'aarch64|aarch64-oe-linux' | sed -n '1p' || true)"

    if [ -z "$LIBGCC_FILE" ] || [ ! -f "$LIBGCC_FILE" ]; then
        echo "[ERROR] libgcc.a not found under $LINUX_DEVKIT" >&2
        exit 1
    fi
}

ensure_inputs() {
    require_dir "$UBOOT_SRC" "U-Boot workspace"
    if [ ! -d "$UBOOT_SRC/.git" ] && [ ! -f "$UBOOT_SRC/.git" ]; then
        echo "[ERROR] Missing U-Boot workspace git repository: $UBOOT_SRC/.git" >&2
        exit 1
    fi
    require_dir "$LINUX_DEVKIT" "linux-devkit"
    require_dir "$K3R5_DEVKIT" "k3r5-devkit"
    require_dir "$PREBUILT_IMAGES" "prebuilt-images directory"
    require_dir "$PREBUILT_DIR" "AM64x prebuilt image directory"
    require_file "$BL31_INPUT" "BL31 binary"
    require_file "$TEE_INPUT" "BL32 binary"
    require_file "$UBOOT_SRC/scripts/config" "U-Boot config helper"

    if [ "$UBOOT_SRC" = "$UBOOT_SDK_SRC" ]; then
        echo "[ERROR] Refusing to build from SDK reference source: $UBOOT_SRC" >&2
        exit 1
    fi

    case "$UBOOT_SRC" in
        "$WORKSPACE_ROOT"/*) ;;
        *)
            echo "[ERROR] Refusing to build outside workspace/: $UBOOT_SRC" >&2
            exit 1
            ;;
    esac

    require_clean_workspace
    sanitize_standalone_env
    mkdir -p "$R5_OUT" "$A53_OUT" "$ARTIFACTS" "$LOG_DIR"
}

run_workspace_verify() {
    ALLOW_DIRTY_WORKSPACE=linux "$VERIFY_SCRIPT"
}

run_r5() {
    rm -rf "$R5_OUT"
    mkdir -p "$R5_OUT"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        am64x_evm_r5_defconfig \
        O="$R5_OUT" | tee "$LOG_DIR/r5-defconfig.log"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        O="$R5_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" \
        -j"$(nproc)" | tee "$LOG_DIR/r5-build.log"
}

run_a53() {
    local enable_watchdog="${1:-0}"

    rm -rf "$A53_OUT"
    mkdir -p "$A53_OUT"
    find_libgcc

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        am64x_evm_a53_defconfig \
        O="$A53_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" | tee "$LOG_DIR/a53-defconfig.log"

    "$UBOOT_SRC/scripts/config" --file "$A53_OUT/.config" \
        -d BOOTEFI_HELLO_COMPILE \
        -d CMD_BOOTEFI_SELFTEST \
        -d EFI_SELFTEST \
        -e EFI_LOAD_FILE2_INITRD

    if [ "$enable_watchdog" = "1" ]; then
        apply_a53_watchdog_config
    fi

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        O="$A53_OUT" \
        olddefconfig | tee "$LOG_DIR/a53-olddefconfig.log"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        PYTHON=/usr/bin/python3 \
        BL31="$BL31_INPUT" \
        TEE="$TEE_INPUT" \
        O="$A53_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" \
        PLATFORM_LIBGCC="$LIBGCC_FILE" \
        -j"$(nproc)" | tee "$LOG_DIR/a53-build.log"
}

collect_artifacts() {
    local tiboot3_src

    mkdir -p "$ARTIFACTS"
    tiboot3_src="$R5_OUT/tiboot3-am64x_sr2-hs-fs-evm.bin"

    if [ ! -f "$tiboot3_src" ]; then
        echo "[ERROR] Expected R5 tiboot3 artifact not found: $tiboot3_src" >&2
        echo "[INFO] Available tiboot3 candidates under $R5_OUT:" >&2
        find "$R5_OUT" -name 'tiboot3*.bin' -print | sort >&2 || true
        exit 1
    fi

    require_file "$A53_OUT/tispl.bin" "tispl.bin"
    require_file "$A53_OUT/u-boot.img" "u-boot.img"

    cp "$tiboot3_src" "$ARTIFACTS/tiboot3.bin"
    cp "$A53_OUT/tispl.bin" "$ARTIFACTS/tispl.bin"
    cp "$A53_OUT/u-boot.img" "$ARTIFACTS/u-boot.img"
}

generate_manifest() {
    local manifest
    local branch

    manifest="$ARTIFACTS/build-manifest.txt"
    branch="$(git -C "$UBOOT_SRC" rev-parse --abbrev-ref HEAD)"

    {
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'SDK_VERSION: %s\n' "$SDK_VERSION"
        printf 'UBOOT_SRC: %s\n' "$UBOOT_SRC"
        printf 'UBOOT_HEAD: %s\n' "$(git -C "$UBOOT_SRC" rev-parse HEAD)"
        printf 'UBOOT_BRANCH: %s\n' "$branch"
        printf 'R5_OUT: %s\n' "$R5_OUT"
        printf 'A53_OUT: %s\n' "$A53_OUT"
        printf 'PREBUILT_DIR: %s\n' "$PREBUILT_DIR"
        printf 'BL31_INPUT: %s\n' "$BL31_INPUT"
        printf 'TEE_INPUT: %s\n' "$TEE_INPUT"
        printf 'BUILD_COMMAND: %s\n' "./tools/build/build-u-boot.sh $ACTION"
        printf '\n[artifact sizes]\n'
        stat -c '%n %s bytes' "$ARTIFACTS/tiboot3.bin" "$ARTIFACTS/tispl.bin" "$ARTIFACTS/u-boot.img"
        printf '\n[sha256]\n'
        sha256sum "$ARTIFACTS/tiboot3.bin" "$ARTIFACTS/tispl.bin" "$ARTIFACTS/u-boot.img"
    } > "$manifest"
}

show_artifacts() {
    ls -lh "$ARTIFACTS/tiboot3.bin" "$ARTIFACTS/tispl.bin" "$ARTIFACTS/u-boot.img"
    sha256sum "$ARTIFACTS/tiboot3.bin" "$ARTIFACTS/tispl.bin" "$ARTIFACTS/u-boot.img"
}

clean_outputs() {
    rm -rf "$R5_OUT" "$A53_OUT" "$ARTIFACTS" "$LOG_DIR"
    echo "[INFO] Removed $BUILD_BASE outputs."
}

case "$ACTION" in
    clean)
        clean_outputs
        ;;
    r5)
        run_workspace_verify
        ensure_inputs
        run_r5
        ;;
    a53)
        run_workspace_verify
        ensure_inputs
        run_a53
        ;;
    artifacts)
        run_workspace_verify
        ensure_inputs
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    a53-watchdog)
        run_workspace_verify
        ensure_inputs
        run_a53 1
        ;;
    all)
        run_workspace_verify
        ensure_inputs
        run_r5
        run_a53
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    all-watchdog)
        run_workspace_verify
        ensure_inputs
        run_r5
        run_a53 1
        collect_artifacts
        generate_manifest
        show_artifacts
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
