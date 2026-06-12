#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
SDK_ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/gen-linux-appimage-for-sbl.sh --print
  ./tools/build/gen-linux-appimage-for-sbl.sh --execute

현재 단계에서는 linuxAppimageGen 입력 후보와 점검 포인트만 출력한다.
`--execute`는 repo-managed staging/work directory에서 local image generation만 수행한다.
EOF
}

if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $ENV_FILE" >&2
    exit 1
fi

if [ ! -f "$SDK_ENV_FILE" ]; then
    echo "[ERROR] SDK env file not found: $SDK_ENV_FILE" >&2
    exit 1
fi

source "$ENV_FILE"
source "$SDK_ENV_FILE"

MODE="${1:---print}"
APPIMAGE_TOOL="$MCU_PLUS_SDK_PATH/tools/boot/linuxAppimageGen"
SDK_PREBUILT_DIR="$SDK_ROOT/board-support/prebuilt-images/am64xx-evm"
LOCAL_UBOOT_ARTIFACT_DIR="$BRINGUP_ROOT/out/u-boot/artifacts"
LOCAL_RAW_SPL="$BRINGUP_ROOT/out/u-boot/a53/spl/u-boot-spl.bin"
STAGING_DIR="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-staging"
WORK_DIR="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-build"

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

stage_inputs() {
    mkdir -p "$STAGING_DIR" "$WORK_DIR"
    cp "$SDK_PREBUILT_DIR/bl31.bin" "$STAGING_DIR/bl31.bin"
    cp "$SDK_PREBUILT_DIR/bl32.bin" "$STAGING_DIR/bl32.bin"
    cp "$LOCAL_RAW_SPL" "$STAGING_DIR/u-boot-spl.bin-am64xx-evm"
    cp "$LOCAL_UBOOT_ARTIFACT_DIR/u-boot.img" "$STAGING_DIR/u-boot.img"
    cp "$APPIMAGE_TOOL/makefile" "$WORK_DIR/makefile"
    cp "$APPIMAGE_TOOL/config.mak" "$WORK_DIR/config.mak"
}

case "$MODE" in
    --print)
        printf 'linuxAppimageGen : %s\n' "$APPIMAGE_TOOL"
        printf 'Expected inputs  : bl31.bin, bl32.bin, u-boot-spl.bin-am64xx-evm, u-boot.img\n'
        printf 'ATF candidate    : %s\n' "$SDK_PREBUILT_DIR/bl31.bin"
        printf 'OPTEE candidate  : %s\n' "$SDK_PREBUILT_DIR/bl32.bin"
        printf 'SPL candidate    : %s\n' "$SDK_PREBUILT_DIR/u-boot-spl.bin-am64xx-evm"
        printf 'Local raw SPL    : %s\n' "$LOCAL_RAW_SPL"
        printf 'Container tispl  : %s\n' "$LOCAL_UBOOT_ARTIFACT_DIR/tispl.bin"
        printf 'U-Boot candidate : %s\n' "$LOCAL_UBOOT_ARTIFACT_DIR/u-boot.img"
        printf 'Staging dir      : %s\n' "$STAGING_DIR"
        printf 'Override vars    : MCU_PLUS_SDK_PATH, PSDK_LINUX_IMAGE_PATH, PSDK_LINUX_PREBUILT_IMAGES\n'
        printf 'Mapping note      : stage local raw SPL as u-boot-spl.bin-am64xx-evm; do not use tispl.bin in linux.mcelf input\n'
        printf 'Policy note       : recommend overriding PSDK_LINUX_PREBUILT_IMAGES to a repo-managed staging directory at execution time\n'
        printf 'Reference note   : linuxAppimageGen/config.mak default SDK path is outdated and must be overridden for SDK 12 repo context\n'
        ;;
    --execute)
        require_file "$SDK_PREBUILT_DIR/bl31.bin"
        require_file "$SDK_PREBUILT_DIR/bl32.bin"
        require_file "$LOCAL_RAW_SPL"
        require_file "$LOCAL_UBOOT_ARTIFACT_DIR/u-boot.img"
        require_file "$APPIMAGE_TOOL/makefile"
        require_file "$APPIMAGE_TOOL/config.mak"
        stage_inputs
        make -C "$WORK_DIR" \
            MCU_PLUS_SDK_PATH="$MCU_PLUS_SDK_PATH" \
            PSDK_LINUX_IMAGE_PATH="$SDK_ROOT" \
            PSDK_LINUX_PREBUILT_IMAGES="$STAGING_DIR" \
            DEVICE_TYPE=GP \
            BOOTIMAGE_FORMAT=mcelf \
            all
        ;;
    *)
        usage
        exit 1
        ;;
esac
