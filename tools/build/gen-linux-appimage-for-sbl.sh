#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$BRINGUP_ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
SDK_ENV_FILE="$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

usage() {
    cat <<'EOF'
Usage:
  ./tools/build/gen-linux-appimage-for-sbl.sh --print [--profile local-fullchain|sdk-prebuilt-mixed]
  ./tools/build/gen-linux-appimage-for-sbl.sh --execute [--profile local-fullchain|sdk-prebuilt-mixed]

현재 단계에서는 linuxAppimageGen 입력 후보와 점검 포인트만 출력한다.
`--execute`는 repo-managed staging/work directory에서 local image generation만 수행한다.

Profiles:
  local-fullchain     local unsigned TF-A/OP-TEE + local U-Boot A53 chain
  sdk-prebuilt-mixed  legacy mixed path using SDK prebuilt BL31/BL32
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

APPIMAGE_TOOL="$MCU_PLUS_SDK_PATH/tools/boot/linuxAppimageGen"
SDK_PREBUILT_DIR="$SDK_ROOT/board-support/prebuilt-images/am64xx-evm"
PROFILE="local-fullchain"
MODE="--print"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --print|--execute)
            MODE="$1"
            ;;
        --profile)
            if [ "$#" -lt 2 ]; then
                echo "[ERROR] Missing value for --profile" >&2
                exit 1
            fi
            PROFILE="$2"
            shift
            ;;
        *)
            usage
            exit 1
            ;;
    esac
    shift
done

PROFILE_LABEL=""
BL31_SRC=""
BL32_SRC=""
SPL_SRC=""
UBOOT_SRC=""
STAGING_DIR=""
WORK_DIR=""
ATF_LOAD_ADDR=""

select_profile() {
    case "$PROFILE" in
        local-fullchain)
            PROFILE_LABEL="local-fullchain"
            BL31_SRC="$BRINGUP_ROOT/workspace/trusted-firmware-a-2.14+git/build/k3/lite/release/bl31.bin"
            BL32_SRC="$BRINGUP_ROOT/workspace/optee-os-4.9.0+git/out/arm-plat-k3/core/tee-pager_v2.bin"
            SPL_SRC="$BRINGUP_ROOT/out/u-boot-local-a53chain/a53/spl/u-boot-spl.bin"
            UBOOT_SRC="$BRINGUP_ROOT/out/u-boot-local-a53chain/a53/u-boot.img"
            ;;
        sdk-prebuilt-mixed)
            PROFILE_LABEL="sdk-prebuilt-mixed"
            BL31_SRC="$SDK_PREBUILT_DIR/bl31.bin"
            BL32_SRC="$SDK_PREBUILT_DIR/bl32.bin"
            SPL_SRC="$BRINGUP_ROOT/out/u-boot/a53/spl/u-boot-spl.bin"
            UBOOT_SRC="$BRINGUP_ROOT/out/u-boot/artifacts/u-boot.img"
            ;;
        *)
            echo "[ERROR] Unsupported profile: $PROFILE" >&2
            exit 1
            ;;
    esac

    STAGING_DIR="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-staging-$PROFILE_LABEL"
    WORK_DIR="$BRINGUP_ROOT/out/r5f-early-boot/linux-appimage-build-$PROFILE_LABEL"
}

select_profile

require_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "[ERROR] Missing file: $path" >&2
        exit 1
    fi
}

sha256_of() {
    sha256sum "$1" | cut -d' ' -f1
}

detect_atf_load_addr() {
    local uboot_build_dir
    local uboot_config

    uboot_build_dir="$(dirname "$(dirname "$SPL_SRC")")"
    uboot_config="$uboot_build_dir/.config"

    if [ -f "$uboot_config" ]; then
        ATF_LOAD_ADDR="$(grep '^CONFIG_K3_ATF_LOAD_ADDR=' "$uboot_config" | cut -d'=' -f2 || true)"
    fi

    if [ -z "$ATF_LOAD_ADDR" ]; then
        ATF_LOAD_ADDR="0x701c0000"
    fi
}

detect_atf_load_addr

write_manifest() {
    local manifest="$WORK_DIR/build-manifest.txt"

    {
        printf 'Profile: %s\n' "$PROFILE_LABEL"
        printf 'Date/time: %s\n' "$(date -Iseconds)"
        printf 'BL31 source: %s\n' "$BL31_SRC"
        printf 'BL32 source: %s\n' "$BL32_SRC"
        printf 'SPL source: %s\n' "$SPL_SRC"
        printf 'U-Boot source: %s\n' "$UBOOT_SRC"
        printf 'ATF load addr: %s\n' "$ATF_LOAD_ADDR"
        printf '\n[source sha256]\n'
        sha256sum "$BL31_SRC" "$BL32_SRC" "$SPL_SRC" "$UBOOT_SRC"
        printf '\n[staged sha256]\n'
        sha256sum "$STAGING_DIR/bl31.bin" "$STAGING_DIR/bl32.bin" "$STAGING_DIR/u-boot-spl.bin-am64xx-evm" "$STAGING_DIR/u-boot.img"
    } > "$manifest"
}

stage_inputs() {
    mkdir -p "$STAGING_DIR" "$WORK_DIR"
    cp "$BL31_SRC" "$STAGING_DIR/bl31.bin"
    cp "$BL32_SRC" "$STAGING_DIR/bl32.bin"
    cp "$SPL_SRC" "$STAGING_DIR/u-boot-spl.bin-am64xx-evm"
    cp "$UBOOT_SRC" "$STAGING_DIR/u-boot.img"
    cp "$APPIMAGE_TOOL/makefile" "$WORK_DIR/makefile"
    cp "$APPIMAGE_TOOL/config.mak" "$WORK_DIR/config.mak"
    sed -i "s/^ATF_LOAD_ADDR=.*/ATF_LOAD_ADDR=${ATF_LOAD_ADDR}/" "$WORK_DIR/config.mak"
    write_manifest
}

case "$MODE" in
    --print)
        printf 'Profile          : %s\n' "$PROFILE_LABEL"
        printf 'linuxAppimageGen : %s\n' "$APPIMAGE_TOOL"
        printf 'Expected inputs  : bl31.bin, bl32.bin, u-boot-spl.bin-am64xx-evm, u-boot.img\n'
        printf 'BL31 source      : %s\n' "$BL31_SRC"
        printf 'BL32 source      : %s\n' "$BL32_SRC"
        printf 'SPL source       : %s\n' "$SPL_SRC"
        printf 'U-Boot source    : %s\n' "$UBOOT_SRC"
        printf 'ATF load addr    : %s\n' "$ATF_LOAD_ADDR"
        printf 'Staging dir      : %s\n' "$STAGING_DIR"
        printf 'Work dir         : %s\n' "$WORK_DIR"
        printf 'Override vars    : MCU_PLUS_SDK_PATH, PSDK_LINUX_IMAGE_PATH, PSDK_LINUX_PREBUILT_IMAGES\n'
        printf 'Mapping note     : stage raw SPL as u-boot-spl.bin-am64xx-evm\n'
        printf 'Reference note   : linuxAppimageGen/config.mak says signed SDK prebuilts are not suitable linux appimage inputs for HS-FS/HS devices\n'
        printf '\n[input sha256]\n'
        sha256sum "$BL31_SRC" "$BL32_SRC" "$SPL_SRC" "$UBOOT_SRC"
        if [ "$PROFILE_LABEL" = "sdk-prebuilt-mixed" ]; then
            printf '\n[warn]\nlegacy mixed profile uses SDK prebuilt BL31/BL32 and should be treated as non-canonical.\n'
        fi
        ;;
    --execute)
        require_file "$BL31_SRC"
        require_file "$BL32_SRC"
        require_file "$SPL_SRC"
        require_file "$UBOOT_SRC"
        require_file "$APPIMAGE_TOOL/makefile"
        require_file "$APPIMAGE_TOOL/config.mak"
        stage_inputs
        make -C "$WORK_DIR" \
            MCU_PLUS_SDK_PATH="$MCU_PLUS_SDK_PATH" \
            PSDK_LINUX_IMAGE_PATH="$SDK_ROOT" \
            PSDK_LINUX_PREBUILT_IMAGES="$STAGING_DIR" \
            BOOTIMAGE_FORMAT=mcelf \
            all
        printf '[OK] linux appimage profile: %s\n' "$PROFILE_LABEL"
        printf '[OK] manifest: %s\n' "$WORK_DIR/build-manifest.txt"
        sha256sum "$WORK_DIR/linux.mcelf.hs_fs" "$WORK_DIR/u-boot.img"
        ;;
    *)
        usage
        exit 1
        ;;
esac
