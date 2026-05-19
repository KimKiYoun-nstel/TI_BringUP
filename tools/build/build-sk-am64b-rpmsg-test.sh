#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
LINUX_ENV="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

ACTION="${1:-all}"
PROFILE="${2:-Release}"

R5F_PROJECT_ROOT="$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/r5f"
A53_PROJECT_ROOT="$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/a53"
CCS_WORKSPACE="$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/ccs_projects"
R5F_PROJECT_NAME="sk_am64b_rpmsg_test_r5fss0_0_freertos_ti_arm_clang"
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

build_r5f() {
    require_file "$MCU_ENV"
    source "$MCU_ENV"
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
    "$CCS_PATH/utils/bin/gmake" -C "$R5F_RELEASE_DIR" -k -j 16 all -O

    require_file "$R5F_RELEASE_DIR/$R5F_PROJECT_NAME.out"
    cp "$R5F_RELEASE_DIR/$R5F_PROJECT_NAME.out" "$BRINGUP_ROOT/out/sk-am64b-rpmsg-test/am64-main-r5f0_0-fw"
}

build_a53() {
    local env_setup="$TI_WORKSPACE/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/linux-devkit/environment-setup"

    require_file "$LINUX_ENV"
    # shellcheck disable=SC1090
    source "$LINUX_ENV"
    require_file "$env_setup"
    # shellcheck disable=SC1090
    source "$env_setup"
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
