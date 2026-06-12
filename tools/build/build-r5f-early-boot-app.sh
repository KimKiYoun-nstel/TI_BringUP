#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
LINUX_ENV="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

PROJECT_SLUG="sk-am64b-r5f-early-boot"
R5F_PROJECT_ROOT="$BRINGUP_ROOT/projects/$PROJECT_SLUG/r5f/draft"
A53_PROJECT_ROOT="$BRINGUP_ROOT/projects/$PROJECT_SLUG/a53"
CCS_WORKSPACE="$BRINGUP_ROOT/out/$PROJECT_SLUG/ccs_projects"
R5F_PROJECT_NAME="sk_am64b_r5f_early_boot_heartbeat_r5fss0_0_freertos_ti_arm_clang"

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

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-r5f-early-boot-app.sh --print
  ./tools/build/build-r5f-early-boot-app.sh r5f [Release|Debug]
  ./tools/build/build-r5f-early-boot-app.sh a53
  ./tools/build/build-r5f-early-boot-app.sh all [Release|Debug]

현재 단계에서는 early-boot firmware source 후보와 재사용 경로만 출력한다.
`r5f` action은 local CCS workspace 기준 buildable draft 검증용이다.
`a53` action은 수동 Linux checker app을 local devkit 기준으로 build 한다.
EOF
}

build_r5f() {
    local profile="${1:-Release}"
    local release_dir

    require_file "$MCU_ENV"
    # shellcheck disable=SC1090
    source "$MCU_ENV"
    require_dir "$CCS_PATH"
    require_dir "$R5F_PROJECT_ROOT/ti-arm-clang"

    release_dir="$CCS_WORKSPACE/$R5F_PROJECT_NAME/$profile"
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
        -ccs.configuration "$profile" || true

    patch_syscfg_ipc_bug "$release_dir/syscfg/ti_drivers_config.c"
    "$CCS_PATH/utils/bin/gmake" -C "$release_dir" -k -j 16 all -O

    require_file "$release_dir/$R5F_PROJECT_NAME.out"
    mkdir -p "$BRINGUP_ROOT/out/$PROJECT_SLUG"
    cp "$release_dir/$R5F_PROJECT_NAME.out" "$BRINGUP_ROOT/out/$PROJECT_SLUG/am64-main-r5f0_0-fw"
}

build_a53() {
    local env_setup
    local had_nounset=0

    require_file "$LINUX_ENV"
    # shellcheck disable=SC1090
    source "$LINUX_ENV"
    env_setup="$TI_WORKSPACE/am64x/ti-processor-sdk-linux-am64xx-evm-12.00.00.07.04/linux-devkit/environment-setup"
    require_file "$env_setup"
    require_dir "$A53_PROJECT_ROOT"
    if [[ $- == *u* ]]; then
        had_nounset=1
        set +u
    fi
    # shellcheck disable=SC1090
    source "$env_setup"
    if [ "$had_nounset" -eq 1 ]; then
        set -u
    fi
    make -C "$A53_PROJECT_ROOT" all CC="$CC"
}

MODE="${1:---print}"

case "$MODE" in
    --print)
        printf 'Primary reuse candidate : %s\n' "$BRINGUP_ROOT/projects/am64x-r5f-hw-control-lab/r5f"
        printf 'Secondary candidate     : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/r5f"
        printf 'Planned target area     : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-r5f-early-boot/r5f/draft"
        printf 'Candidate set A         : %s\n' "$BRINGUP_ROOT/projects/am64x-r5f-hw-control-lab/r5f/main.c"
        printf 'Candidate set A         : %s\n' "$BRINGUP_ROOT/projects/am64x-r5f-hw-control-lab/r5f/example.syscfg"
        printf 'Candidate set A         : %s\n' "$BRINGUP_ROOT/projects/am64x-r5f-hw-control-lab/r5f/ipc_rpmsg_echo.c"
        printf 'Candidate set B         : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/r5f/main.c"
        printf 'Candidate set B         : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/r5f/example.syscfg"
        printf 'Candidate set B         : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-rpmsg-test/r5f/ipc_rpmsg_echo.c"
        printf 'Draft layout note       : %s\n' "$BRINGUP_ROOT/projects/sk-am64b-r5f-early-boot/r5f/draft/README.md"
        printf 'A53 checker source      : %s\n' "$A53_PROJECT_ROOT/src/main.c"
        printf 'A53 checker output      : %s\n' "$BRINGUP_ROOT/out/$PROJECT_SLUG/a53/sk_am64b_r5f_early_boot_check"
        printf 'Selection note          : start from set A for SHM/heartbeat direction, fall back to set B for minimal Linux IPC echo baseline\n'
        ;;
    r5f)
        build_r5f "${2:-Release}"
        ;;
    a53)
        build_a53
        ;;
    all)
        build_r5f "${2:-Release}"
        build_a53
        ;;
    *)
        usage
        exit 1
        ;;
esac
