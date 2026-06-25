#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SDK_ENV="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

if [ ! -f "$SDK_ENV" ]; then
    echo "[ERROR] Env file not found: $SDK_ENV" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$SDK_ENV"

TFA_SRC="$BRINGUP_ROOT/workspace/trusted-firmware-a-2.14+git"
OPTEE_SRC="$BRINGUP_ROOT/workspace/optee-os-4.9.0+git"
UBOOT_SRC_CLEAN="$BRINGUP_ROOT/workspace/ti-u-boot-sdk12-sk-am64b-local-fullchain"
UBOOT_BUILD_BASE="$BRINGUP_ROOT/out/u-boot-local-a53chain"
OPTEE_TA32_SYSROOT="$TI_WORKSPACE/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/k3r5-devkit/sysroots/armv7at2hf-vfp-oe-eabi"
TFA_OUT="$TFA_SRC/build/k3/lite/release/bl31.bin"
OPTEE_OUT="$OPTEE_SRC/out/arm-plat-k3/core/tee-pager_v2.bin"
UBOOT_OUT_DIR="$UBOOT_BUILD_BASE/a53"
SPL_OUT="$UBOOT_OUT_DIR/spl/u-boot-spl.bin"
UBOOT_OUT="$UBOOT_OUT_DIR/u-boot.img"
WATCHDOG_CONFIG="$BRINGUP_ROOT/bsp/u-boot/configs/am64x-watchdog.config"

require_dir() {
    local path="$1"
    if [ ! -d "$path" ]; then
        echo "[ERROR] Missing directory: $path" >&2
        exit 1
    fi
}

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --print
  ./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-tfa
  ./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-optee
  ./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-uboot-a53
  ./tools/build/bootstrap-sk-am64b-sbl-ospi-linux-local-fullchain.sh --build-all

This helper codifies the source-bootstrap side of the project.
It rebuilds partial A53-chain outputs from workspace source trees, not the final flash set.
EOF
}

print_plan() {
    printf 'Source bootstrap scope : TF-A -> OP-TEE -> U-Boot A53 partial outputs\n'
    printf 'TF-A source            : %s\n' "$TFA_SRC"
    printf 'TF-A output            : %s\n' "$TFA_OUT"
    printf 'OP-TEE source          : %s\n' "$OPTEE_SRC"
    printf 'OP-TEE output          : %s\n' "$OPTEE_OUT"
    printf 'U-Boot source          : %s\n' "$UBOOT_SRC_CLEAN"
    printf 'U-Boot out base        : %s\n' "$UBOOT_BUILD_BASE"
    printf 'U-Boot SPL output      : %s\n' "$SPL_OUT"
    printf 'U-Boot image output    : %s\n' "$UBOOT_OUT"
    printf 'TF-A project delta     : none verified; current project consumes local unsigned bl31.bin as input\n'
    printf 'OP-TEE project delta   : none verified; current project consumes local tee-pager_v2.bin as input\n'
    printf 'U-Boot A53 baseline    : clean worktree on bootdelay=10 source baseline + watchdog config fragment %s\n' "$WATCHDOG_CONFIG"
    printf 'Important boundary     : this helper builds partial source outputs only. Final flash-image assembly is handled by build-sk-am64b-sbl-ospi-linux-local-fullchain.sh\n'
}

build_tfa() {
    require_dir "$TFA_SRC"
    make -C "$TFA_SRC" CROSS_COMPILE="$CROSS_COMPILE_AARCH64" ARCH=aarch64 PLAT=k3 TARGET_BOARD=lite SPD=opteed ENABLE_FEAT_MPAM=0 all -j"$(nproc)"
}

build_optee() {
    require_dir "$OPTEE_SRC"
    require_dir "$OPTEE_TA32_SYSROOT"
    make -C "$OPTEE_SRC" ARCH=arm \
        CROSS_COMPILE="$CROSS_COMPILE_ARMV7R" \
        CROSS_COMPILE32="$CROSS_COMPILE_ARMV7R" \
        CROSS_COMPILE64="$CROSS_COMPILE_AARCH64" \
        CFLAGS32="--sysroot=$OPTEE_TA32_SYSROOT" \
        CXXFLAGS32="--sysroot=$OPTEE_TA32_SYSROOT" \
        PLATFORM=k3 PLATFORM_FLAVOR=am64x CFG_ARM64_core=y -j"$(nproc)"
}

build_uboot_a53() {
    require_dir "$UBOOT_SRC_CLEAN"
    require_dir "$TFA_SRC"
    require_dir "$OPTEE_SRC"
    require_file "$WATCHDOG_CONFIG"
    UBOOT_SRC_OVERRIDE="$UBOOT_SRC_CLEAN" \
    BL31_BIN="$TFA_OUT" \
    TEE_BIN="$OPTEE_OUT" \
    UBOOT_BUILD_BASE="$UBOOT_BUILD_BASE" \
    "$BRINGUP_ROOT/tools/build/build-u-boot.sh" a53-watchdog
}

MODE="${1:---print}"

case "$MODE" in
    --print)
        print_plan
        ;;
    --build-tfa)
        build_tfa
        ;;
    --build-optee)
        build_optee
        ;;
    --build-uboot-a53)
        build_uboot_a53
        ;;
    --build-all)
        build_tfa
        build_optee
        build_uboot_a53
        ;;
    *)
        usage
        exit 1
        ;;
esac
