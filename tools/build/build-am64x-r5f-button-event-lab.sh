#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
LINUX_ENV="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"
VERIFY_SCRIPT="$BRINGUP_ROOT/tools/prepare/verify-workspace-state.sh"

ACTION="${1:-all}"
PROFILE="${2:-Release}"

if [ ! -x "$VERIFY_SCRIPT" ]; then
    echo "[ERROR] Verification script is missing or not executable: $VERIFY_SCRIPT" >&2
    exit 1
fi

"$VERIFY_SCRIPT"

PROJECT_SLUG="am64x-r5f-button-event-lab"
R5F_PROJECT_ROOT="$BRINGUP_ROOT/projects/$PROJECT_SLUG/r5f"
A53_PROJECT_ROOT="$BRINGUP_ROOT/projects/$PROJECT_SLUG/a53"
CCS_WORKSPACE="$BRINGUP_ROOT/out/$PROJECT_SLUG/ccs_projects"
R5F_PROJECT_NAME="am64x_r5f_button_event_lab_r5fss0_0_freertos_ti_arm_clang"
R5F_RELEASE_DIR="$CCS_WORKSPACE/$R5F_PROJECT_NAME/$PROFILE"

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

require_dir() {
    local path="$1"
    if [ ! -d "$path" ]; then
        echo "[ERROR] Missing directory: $path" >&2
        exit 1
    fi
}

patch_syscfg_ipc_bug() {
    local generated="$1"
    if [ ! -f "$generated" ]; then
        return 0
    fi
    perl -0pi -e 's/\&gIpcSharedMem\[\]/\&gIpcSharedMem[0]/g' "$generated"
}

patch_syscfg_gpio_route() {
    local generated_dir="$1"
    local generated_h="$generated_dir/ti_drivers_config.h"
    local generated_c="$generated_dir/ti_drivers_config.c"

    if [ -f "$generated_h" ]; then
        perl -0pi -e 's/CSLR_R5FSS0_CORE0_INTR_MAIN_GPIOMUX_INTROUTER0_OUTP_0/CSLR_R5FSS0_CORE0_INTR_MCU_MCU_GPIOMUX_INTROUTER0_OUTP_0/g' "$generated_h"
    fi

    if [ -f "$generated_c" ]; then
        perl -0pi -e 's/CSLR_R5FSS0_CORE0_INTR_MAIN_GPIOMUX_INTROUTER0_OUTP_0/CSLR_R5FSS0_CORE0_INTR_MCU_MCU_GPIOMUX_INTROUTER0_OUTP_0/g' "$generated_c"
    fi
}

build_r5f() {
    require_file "$MCU_ENV"
    set +u
    # shellcheck disable=SC1090
    source "$MCU_ENV"
    set -u
    require_dir "$CCS_PATH"

    mkdir -p "$CCS_WORKSPACE"

    "$CCS_PATH/eclipse/ccs-server-cli.sh" \
        -workspace "$CCS_WORKSPACE" \
        -application com.ti.ccs.apps.projectCreate \
        -ccs.projectSpec "$R5F_PROJECT_ROOT/ti-arm-clang/example.projectspec" \
        -ccs.overwrite full

    "$CCS_PATH/eclipse/ccs-server-cli.sh" \
        -workspace "$CCS_WORKSPACE" \
        -application com.ti.ccs.apps.projectBuild \
        -ccs.projects "$R5F_PROJECT_NAME" \
        -ccs.configuration "$PROFILE" || true

    patch_syscfg_ipc_bug "$R5F_RELEASE_DIR/syscfg/ti_drivers_config.c"
    patch_syscfg_gpio_route "$R5F_RELEASE_DIR/syscfg"
    "$CCS_PATH/utils/bin/gmake" -C "$R5F_RELEASE_DIR" -k -j 16 all -O

    require_file "$R5F_RELEASE_DIR/$R5F_PROJECT_NAME.out"
    cp "$R5F_RELEASE_DIR/$R5F_PROJECT_NAME.out" "$BRINGUP_ROOT/out/$PROJECT_SLUG/am64-main-r5f0_0-fw"
}

build_a53() {
    local env_setup

    require_file "$LINUX_ENV"
    set +u
    # shellcheck disable=SC1090
    source "$LINUX_ENV"
    set -u
    env_setup="$TI_WORKSPACE/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/linux-devkit/environment-setup"
    require_file "$env_setup"
    set +u
    # shellcheck disable=SC1090
    source "$env_setup"
    set -u
    make -C "$A53_PROJECT_ROOT" all \
        CC="$CC" \
        SDKTARGETSYSROOT="$SDKTARGETSYSROOT" \
        LINUX_DEVKIT="$LINUX_DEVKIT"
}

case "$ACTION" in
    r5f)
        build_r5f
        ;;
    a53)
        build_a53
        ;;
    all)
        build_r5f
        build_a53
        ;;
    *)
        echo "Usage: $0 {r5f|a53|all} [Release|Debug]" >&2
        exit 1
        ;;
esac
