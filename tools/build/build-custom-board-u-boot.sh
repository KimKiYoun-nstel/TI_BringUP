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

BUILD_BASE="$BRINGUP_ROOT/out/u-boot-custom-board/$BOARD/$PURPOSE"
R5_OUT="$BUILD_BASE/r5"
A53_OUT="$BUILD_BASE/a53"
ARTIFACTS="$BUILD_BASE/artifacts"
LOG_DIR="$BUILD_BASE/logs"
PREBUILT_DIR=""
BINMAN_DTSI_REL="arch/arm/dts/k3-am64x-binman.dtsi"
R5_DTB_REL="../r5/spl/dts/k3-am6412-cpu-brd-v03-pba-r5.dtb"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-custom-board-u-boot.sh r5
  ./tools/build/build-custom-board-u-boot.sh a53
  ./tools/build/build-custom-board-u-boot.sh all
  ./tools/build/build-custom-board-u-boot.sh artifacts
EOF
}

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"

PREBUILT_DIR="$PREBUILT_IMAGES/am64xx-evm"

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
    require_dir "$UBOOT_SRC" "U-Boot workspace"
    require_dir "$UBOOT_SRC/.git" "U-Boot workspace git repository"
    require_dir "$LINUX_DEVKIT" "linux-devkit"
    require_dir "$K3R5_DEVKIT" "k3r5-devkit"
    require_dir "$PREBUILT_DIR" "AM64x prebuilt image directory"
    require_file "$PREBUILT_DIR/bl31.bin" "BL31 binary"
    require_file "$PREBUILT_DIR/bl32.bin" "BL32 binary"
    require_file "$UBOOT_SRC/scripts/config" "U-Boot config helper"
    require_file "$SYNC_HELPER" "custom board DTS sync helper"

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

    sanitize_standalone_env
    mkdir -p "$R5_OUT" "$A53_OUT" "$ARTIFACTS" "$LOG_DIR"
}

prepare_workspace_projection() {
    if [ -x "$VERIFY_SCRIPT" ]; then
        ALLOW_DIRTY_WORKSPACE=1 "$VERIFY_SCRIPT"
    fi

    "$SYNC_HELPER" u-boot "$BOARD" "$PURPOSE"
}

patch_binman_for_custom_board() {
    local binman_file="$UBOOT_SRC/$BINMAN_DTSI_REL"

    require_file "$binman_file" "U-Boot binman DTSI"

    perl -0pi -e 's@#define SPL_AM642_EVM_DTB ".*"@#define SPL_AM642_EVM_DTB "../r5/spl/dts/k3-am6412-cpu-brd-v03-pba-r5.dtb"@' "$binman_file"
    perl -0pi -e 's@#define SPL_AM642_SK_DTB ".*"@#define SPL_AM642_SK_DTB "../r5/spl/dts/k3-am6412-cpu-brd-v03-pba-r5.dtb"@' "$binman_file"
    perl -0pi -e 's@#define AM642_EVM_DTB ".*"@#define AM642_EVM_DTB "u-boot.dtb"@' "$binman_file"
    perl -0pi -e 's@#define AM642_SK_DTB ".*"@#define AM642_SK_DTB "u-boot.dtb"@' "$binman_file"
}

apply_r5_config_overrides() {
    "$UBOOT_SRC/scripts/config" --file "$R5_OUT/.config" \
        --set-str DEFAULT_DEVICE_TREE "k3-am6412-cpu-brd-v03-pba-r5" \
        --set-str SPL_OF_LIST "k3-am6412-cpu-brd-v03-pba-r5" \
        --set-val SYS_MMCSD_RAW_MODE_U_BOOT_SECTOR 0x400
}

apply_a53_config_overrides() {
    "$UBOOT_SRC/scripts/config" --file "$A53_OUT/.config" \
        --set-str DEFAULT_DEVICE_TREE "ti/k3-am6412-cpu-brd-v03-pba" \
        --set-str OF_LIST "ti/k3-am6412-cpu-brd-v03-pba" \
        --set-val SYS_MMCSD_RAW_MODE_U_BOOT_SECTOR 0x1400
}

find_libgcc() {
    LIBGCC_FILE="$(find "$LINUX_DEVKIT" -name "libgcc.a" -print 2>/dev/null | grep -E 'aarch64|aarch64-oe-linux' | sed -n '1p' || true)"

    if [ -z "$LIBGCC_FILE" ] || [ ! -f "$LIBGCC_FILE" ]; then
        echo "[ERROR] libgcc.a not found under $LINUX_DEVKIT" >&2
        exit 1
    fi
}

run_r5() {
    rm -rf "$R5_OUT"
    mkdir -p "$R5_OUT"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        am64x_evm_r5_defconfig \
        O="$R5_OUT" | tee "$LOG_DIR/r5-defconfig.log"

    apply_r5_config_overrides

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        O="$R5_OUT" \
        olddefconfig | tee "$LOG_DIR/r5-olddefconfig.log"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        O="$R5_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" \
        -j"$(nproc)" | tee "$LOG_DIR/r5-build.log"
}

run_a53() {
    rm -rf "$A53_OUT"
    mkdir -p "$A53_OUT"
    find_libgcc

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        am64x_evm_a53_defconfig \
        O="$A53_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" | tee "$LOG_DIR/a53-defconfig.log"

    apply_a53_config_overrides

    "$UBOOT_SRC/scripts/config" --file "$A53_OUT/.config" \
        -d BOOTEFI_HELLO_COMPILE \
        -d CMD_BOOTEFI_SELFTEST \
        -d EFI_SELFTEST \
        -e EFI_LOAD_FILE2_INITRD

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        O="$A53_OUT" \
        olddefconfig | tee "$LOG_DIR/a53-olddefconfig.log"

    make -C "$UBOOT_SRC" \
        ARCH=arm CROSS_COMPILE="$CROSS_COMPILE_AARCH64" \
        PYTHON=/usr/bin/python3 \
        BL31="$PREBUILT_DIR/bl31.bin" \
        TEE="$PREBUILT_DIR/bl32.bin" \
        O="$A53_OUT" \
        BINMAN_INDIRS="$PREBUILT_DIR" \
        PLATFORM_LIBGCC="$LIBGCC_FILE" \
        -j"$(nproc)" | tee "$LOG_DIR/a53-build.log"
}

collect_artifacts() {
    local tiboot3_src="$R5_OUT/tiboot3-am64x_sr2-hs-fs-evm.bin"

    require_file "$tiboot3_src" "tiboot3 custom board artifact"
    require_file "$A53_OUT/tispl.bin" "tispl.bin"
    require_file "$A53_OUT/u-boot.img" "u-boot.img"

    cp "$tiboot3_src" "$ARTIFACTS/tiboot3.bin"
    cp "$A53_OUT/tispl.bin" "$ARTIFACTS/tispl.bin"
    cp "$A53_OUT/u-boot.img" "$ARTIFACTS/u-boot.img"
}

generate_manifest() {
    local manifest="$ARTIFACTS/build-manifest.txt"
    local branch

    branch="$(git -C "$UBOOT_SRC" rev-parse --abbrev-ref HEAD)"

    {
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'SDK_VERSION: %s\n' "$SDK_VERSION"
        printf 'BOARD: %s\n' "$BOARD"
        printf 'PURPOSE: %s\n' "$PURPOSE"
        printf 'UBOOT_SRC: %s\n' "$UBOOT_SRC"
        printf 'UBOOT_HEAD: %s\n' "$(git -C "$UBOOT_SRC" rev-parse HEAD)"
        printf 'UBOOT_BRANCH: %s\n' "$branch"
        printf 'DTS_SET_LINUX: %s\n' "$BRINGUP_ROOT/bsp/linux/dts/custom-board/$BOARD/sets/$PURPOSE"
        printf 'DTS_SET_UBOOT: %s\n' "$BRINGUP_ROOT/bsp/u-boot/dts/custom-board/$BOARD/sets/$PURPOSE"
        printf 'SYNC_HELPER: %s\n' "$SYNC_HELPER u-boot $BOARD $PURPOSE"
        printf 'A53_CONFIG_OVERRIDE: %s\n' "$BRINGUP_ROOT/bsp/u-boot/configs/custom-board/$BOARD/bringup-default-a53.config"
        printf 'R5_CONFIG_OVERRIDE: %s\n' "$BRINGUP_ROOT/bsp/u-boot/configs/custom-board/$BOARD/bringup-default-r5.config"
        printf 'BINMAN_MACRO_PATCH: %s\n' "$BINMAN_DTSI_REL -> $R5_DTB_REL and u-boot.dtb"
        printf 'BOOT_POLICY: %s\n' 'eMMC-first Linux boot via mmc0/sdhci0; OSPI kept as fallback hardware candidate'
        printf 'EMMC_RAW_LAYOUT: %s\n' 'tiboot3@0x0 tispl@0x400 u-boot.img@0x1400 within 4MiB boot partition candidate'
        printf 'BUILD_COMMAND: %s\n' "./tools/build/build-custom-board-u-boot.sh $ACTION"
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

ensure_inputs
prepare_workspace_projection
patch_binman_for_custom_board

case "$ACTION" in
    r5)
        run_r5
        ;;
    a53)
        run_a53
        ;;
    all)
        run_r5
        run_a53
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
