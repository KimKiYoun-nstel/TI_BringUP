#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    echo "[INFO] Copy tools/env/mcu-plus-sdk-am64x-12.00.00.env.example first." >&2
    exit 1
fi

source "$ENV_FILE"

ACTION="${1:-}"
TARGET="${2:-}"
PROFILE="${3:-release}"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/build-mcu-plus-example.sh make <relative-example-dir> [profile]
  ./tools/build/build-mcu-plus-example.sh ccs-export <relative-example-dir>
  ./tools/build/build-mcu-plus-example.sh ccs-build <ccs-project-name> [profile]

Examples:
  ./tools/build/build-mcu-plus-example.sh make examples/hello_world/am64x-sk/r5fss0-0_freertos/ti-arm-clang release
  ./tools/build/build-mcu-plus-example.sh ccs-export examples/drivers/ipc/ipc_rpmsg_echo/am64x-sk/r5fss0-0_freertos/ti-arm-clang
  ./tools/build/build-mcu-plus-example.sh ccs-build hello_world_am64x-sk_r5fss0-0_freertos_ti-arm-clang Release
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

check_env() {
    "$SCRIPT_DIR/check-mcu-plus-env.sh" >/dev/null
}

check_env

case "$ACTION" in
    make|ccs-export)
        if [ -z "$TARGET" ]; then
            usage
            exit 1
        fi
        EXAMPLE_DIR="$MCU_PLUS_SDK_PATH/$TARGET"
        require_dir "$EXAMPLE_DIR" "MCU+ example directory"
        ;;
    ccs-build)
        if [ -z "$TARGET" ]; then
            usage
            exit 1
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac

case "$ACTION" in
    make)
        make -C "$EXAMPLE_DIR" MCU_PLUS_SDK_PATH="$MCU_PLUS_SDK_PATH" PROFILE="$PROFILE"
        ;;
    ccs-export)
        make -f makefile_projectspec -C "$EXAMPLE_DIR" export MCU_PLUS_SDK_PATH="$MCU_PLUS_SDK_PATH"
        ;;
    ccs-build)
        "$CCS_PATH/eclipse/ccs-server-cli.sh" \
            -workspace "$MCU_PLUS_CCS_PROJECTS_DIR" \
            -application com.ti.ccs.apps.projectBuild \
            -ccs.projects "$TARGET" \
            -ccs.configuration "$PROFILE"
        ;;
esac
