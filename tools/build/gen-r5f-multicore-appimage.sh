#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"

PROJECT_SLUG="sk-am64b-r5f-early-boot"
R5F_ELF="$BRINGUP_ROOT/out/$PROJECT_SLUG/am64-main-r5f0_0-fw"
OUT_DIR="$BRINGUP_ROOT/out/$PROJECT_SLUG/images"
MCELF_NAME="r5f-early-heartbeat.mcelf"
MCELF_HS_FS_NAME="$MCELF_NAME.hs_fs"
CORE_ID_R5FSS0_0=4
DEV_ID=55

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/gen-r5f-multicore-appimage.sh --print
  ./tools/build/gen-r5f-multicore-appimage.sh --execute

Generate a local R5F multicore ELF/appimage candidate from the early-boot draft ELF.
This does not flash or interact with the board.
EOF
}

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

if [ ! -f "$MCU_ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $MCU_ENV_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$MCU_ENV_FILE"

MCELF_IMAGE_GEN="$MCU_PLUS_SDK_PATH/tools/boot/multicore-elf/genimage_am64x.py"
APP_IMAGE_SIGN_CMD="$MCU_PLUS_SDK_PATH/source/security/security_common/tools/boot/signing/appimage_x509_cert_gen.py"
SIGNING_TOOL_PATH="$MCU_PLUS_SDK_PATH/source/security/security_common/tools/boot/signing"
APP_SIGNING_KEY="$SIGNING_TOOL_PATH/app_degenerateKey.pem"

MODE="${1:---print}"

case "$MODE" in
    --print)
        printf 'Mode               : print only\n'
        printf 'Draft ELF          : %s\n' "$R5F_ELF"
        printf 'Output dir         : %s\n' "$OUT_DIR"
        printf 'MCELF tool         : %s\n' "$MCELF_IMAGE_GEN"
        printf 'Sign tool          : %s\n' "$APP_IMAGE_SIGN_CMD"
        printf 'Signing key        : %s\n' "$APP_SIGNING_KEY"
        printf 'Core/Dev IDs       : r5fss0-0=%s dev=%s\n' "$CORE_ID_R5FSS0_0" "$DEV_ID"
        printf 'Outputs            : %s, %s\n' "$MCELF_NAME" "$MCELF_HS_FS_NAME"
        ;;
    --execute)
        require_file "$R5F_ELF"
        require_file "$MCELF_IMAGE_GEN"
        require_file "$APP_IMAGE_SIGN_CMD"
        require_file "$APP_SIGNING_KEY"
        mkdir -p "$OUT_DIR"
        python3 "$MCELF_IMAGE_GEN" --core-img="$CORE_ID_R5FSS0_0:$R5F_ELF" --output="$OUT_DIR/$MCELF_NAME"
        python3 "$APP_IMAGE_SIGN_CMD" --bin "$OUT_DIR/$MCELF_NAME" --authtype 1 --key "$APP_SIGNING_KEY" --output "$OUT_DIR/$MCELF_HS_FS_NAME"
        ;;
    *)
        usage
        exit 1
        ;;
esac
