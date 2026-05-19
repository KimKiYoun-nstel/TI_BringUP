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

require_dir() {
    local path="$1"
    local label="$2"

    if [ ! -d "$path" ]; then
        echo "[ERROR] Missing $label: $path" >&2
        exit 1
    fi
}

require_exec() {
    local path="$1"
    local label="$2"

    if [ ! -x "$path" ]; then
        echo "[ERROR] Missing executable $label: $path" >&2
        exit 1
    fi
}

require_dir "$MCU_PLUS_SDK_INSTALL_ROOT" "MCU+ SDK install root"
require_dir "$MCU_PLUS_SDK_PATH" "MCU+ SDK workspace root"
require_dir "$MCU_PLUS_CCS_PROJECTS_DIR" "MCU+ CCS projects directory"
require_dir "$CCS_PATH" "CCS install root"
require_dir "$SYSCFG_PATH" "SysConfig root"
require_dir "$CGT_TI_ARM_CLANG_PATH" "TI ARM CLANG root"
require_dir "$CGT_GCC_AARCH64_PATH" "AArch64 GNU bare-metal toolchain"

require_exec "$CCS_PATH/eclipse/ccs-server-cli.sh" "CCS headless CLI"
require_exec "$SYSCFG_PATH/sysconfig_cli.sh" "SysConfig CLI"
require_exec "$CGT_TI_ARM_CLANG_PATH/bin/tiarmclang" "TI ARM CLANG"
require_exec "$CGT_GCC_AARCH64_PATH/bin/aarch64-none-elf-gcc" "AArch64 GNU GCC"

case "$MCU_PLUS_SDK_PATH" in
    "$BRINGUP_ROOT"/workspace/*) ;;
    *)
        echo "[ERROR] MCU_PLUS_SDK_PATH is outside workspace/: $MCU_PLUS_SDK_PATH" >&2
        exit 1
        ;;
esac

echo "[OK] MCU+ SDK workspace env is ready."
echo "      install root : $MCU_PLUS_SDK_INSTALL_ROOT"
echo "      workspace    : $MCU_PLUS_SDK_PATH"
echo "      ccs projects : $MCU_PLUS_CCS_PROJECTS_DIR"
echo "      CCS          : $CCS_PATH"
echo "      SysConfig    : $SYSCFG_PATH"
echo "      TI CLANG     : $CGT_TI_ARM_CLANG_PATH"
echo "      A53 GCC      : $CGT_GCC_AARCH64_PATH"
