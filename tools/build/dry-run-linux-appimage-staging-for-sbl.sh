#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCU_ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
SDK_ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/dry-run-linux-appimage-staging-for-sbl.sh --dry-run

이 스크립트는 linuxAppimageGen용 staging policy를 검증/출력만 한다.
copy, symlink, make, linuxAppimageGen 실행은 수행하지 않는다.
EOF
}

print_entry() {
    local label="$1"
    local source_path="$2"
    local staging_path="$3"
    local alias_note="$4"

    printf '%s\n' "[$label]"
    printf '  source   : %s\n' "$source_path"
    printf '  staging  : %s\n' "$staging_path"
    printf '  alias    : %s\n' "$alias_note"

    if [ -f "$source_path" ]; then
        printf '  exists   : yes\n'
        printf '  size     : %s bytes\n' "$(stat -c '%s' "$source_path")"
        printf '  sha256   : %s\n' "$(sha256sum "$source_path" | cut -d' ' -f1)"
    else
        printf '  exists   : no\n'
        printf '  size     : n/a\n'
        printf '  sha256   : n/a\n'
    fi
}

if [ ! -f "$MCU_ENV_FILE" ]; then
    echo "[ERROR] Env file not found: $MCU_ENV_FILE" >&2
    exit 1
fi

if [ ! -f "$SDK_ENV_FILE" ]; then
    echo "[ERROR] SDK env file not found: $SDK_ENV_FILE" >&2
    exit 1
fi

source "$MCU_ENV_FILE"
source "$SDK_ENV_FILE"

MODE="${1:---dry-run}"
APPIMAGE_TOOL="$MCU_PLUS_SDK_PATH/tools/boot/linuxAppimageGen"
SDK_PREBUILT_DIR="$SDK_ROOT/board-support/prebuilt-images/am64xx-evm"
LOCAL_UBOOT_ARTIFACT_DIR="$BRINGUP_ROOT/out/u-boot/artifacts"
STAGING_DIR="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-staging"

case "$MODE" in
    --dry-run)
        printf 'Mode                    : dry-run only\n'
        printf 'MCU+ workspace          : %s\n' "$MCU_PLUS_SDK_PATH"
        printf 'SDK root                : %s\n' "$SDK_ROOT"
        printf 'linuxAppimageGen        : %s\n' "$APPIMAGE_TOOL"
        printf 'Staging dir             : %s\n' "$STAGING_DIR"
        printf 'Operation policy        : print planned staging only; no copy, symlink, make, or linuxAppimageGen execution\n'
        printf '\n'
        print_entry 'bl31.bin' \
            "$SDK_PREBUILT_DIR/bl31.bin" \
            "$STAGING_DIR/bl31.bin" \
            'no'
        printf '\n'
        print_entry 'bl32.bin' \
            "$SDK_PREBUILT_DIR/bl32.bin" \
            "$STAGING_DIR/bl32.bin" \
            'no'
        printf '\n'
        print_entry 'u-boot-spl.bin-am64xx-evm' \
            "$LOCAL_UBOOT_ARTIFACT_DIR/tispl.bin" \
            "$STAGING_DIR/u-boot-spl.bin-am64xx-evm" \
            'yes, source canonical name is tispl.bin'
        printf '\n'
        print_entry 'u-boot.img' \
            "$LOCAL_UBOOT_ARTIFACT_DIR/u-boot.img" \
            "$STAGING_DIR/u-boot.img" \
            'no'
        printf '\n'
        printf 'Override vars           : MCU_PLUS_SDK_PATH=%s\n' "$MCU_PLUS_SDK_PATH"
        printf 'Override vars           : PSDK_LINUX_IMAGE_PATH=%s\n' "$SDK_ROOT"
        printf 'Override vars           : PSDK_LINUX_PREBUILT_IMAGES=%s\n' "$STAGING_DIR"

        if [ -f "$SDK_PREBUILT_DIR/bl31.bin" ] && [ -f "$SDK_PREBUILT_DIR/bl32.bin" ] && [ -f "$LOCAL_UBOOT_ARTIFACT_DIR/tispl.bin" ] && [ -f "$LOCAL_UBOOT_ARTIFACT_DIR/u-boot.img" ]; then
            printf 'Validation result       : pass\n'
        else
            printf 'Validation result       : fail\n'
        fi

        printf 'Notes                   : this helper does not create the staging directory\n'
        printf 'Notes                   : this helper does not run linuxAppimageGen\n'
        printf 'Notes                   : stage SPL with alias u-boot-spl.bin-am64xx-evm while keeping tispl.bin as local source of truth\n'
        ;;
    *)
        usage
        exit 1
        ;;
esac
