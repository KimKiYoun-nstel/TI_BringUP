#!/usr/bin/env bash
# Reconstruct sources from target-installed packages and selected Git patches.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:---print}" != --execute ]]; then
    printf '%s\n' 'Usage: bash tools/prepare/reconstruct-host-workspaces.sh --execute' \
        'Requires SDK/MCU+ installers already run on this host and empty destination source paths.' \
        'Creates kernel baseline, U-Boot default/fullchain, MCU+ C Case, TF-A and OP-TEE topics.'
    exit 0
fi
source "$ROOT/tools/env/sdk-12.00.00.07.04.env"
source "$ROOT/tools/env/mcu-plus-sdk-am64x-12.00.00.env"
export GIT_COMMITTER_NAME="Workspace Reconstruction"
export GIT_COMMITTER_EMAIL="noreply@example.com"
export GIT_AUTHOR_NAME="$GIT_COMMITTER_NAME"
export GIT_AUTHOR_EMAIL="$GIT_COMMITTER_EMAIL"

UBASE=2549829cc194ffd9e38b755d2e10c7fc4cd971eb
KBASE=c214492085504176b9c252a7175e4e60b4b442af
TFA_HEAD=44fcd9c2d62460a780a5e76f6e65202c37d8dbb7
OPTEE_HEAD=60706ecef7619a01c5f5da20ea12a832699a1440
SEED="$TI_WORKSPACE/local_git_repo/mcu_plus_sdk_am64x_12_00_00_27.git"

for name in ti-u-boot-sdk12 ti-u-boot-sdk12-sk-am64b-local-fullchain \
    ti-linux-kernel-sdk12 mcu_plus_sdk_am64x_12_00_00_27 \
    trusted-firmware-a-2.14+git optee-os-4.9.0+git; do
    if [[ -e "$WORKSPACE_ROOT/$name" ]]; then
        printf '[ERROR] Destination already exists: %s\n' "$WORKSPACE_ROOT/$name" >&2
        exit 1
    fi
done
[[ ! -e "$SEED" ]] || { printf '[ERROR] Seed exists: %s\n' "$SEED" >&2; exit 1; }
[[ -d "$MCU_PLUS_SDK_INSTALL_ROOT" && -d "$BOARD_SUPPORT" ]]
mkdir -p "$WORKSPACE_ROOT" "$TI_WORKSPACE/local_git_repo"

clone_sdk() {
    local name="$1" sdk_name="$2" commit="$3" upstream="${4:-}"
    local dest="$WORKSPACE_ROOT/$name"
    git clone --no-hardlinks --no-checkout "$BOARD_SUPPORT/$sdk_name" "$dest"
    if ! git -C "$dest" cat-file -e "$commit^{commit}" 2>/dev/null; then
        [[ -n "$upstream" ]]
        git -C "$dest" fetch --no-tags "$upstream" "$commit"
    fi
    git -C "$dest" switch -c migration-reconstructed "$commit"
}

clone_sdk ti-linux-kernel-sdk12 ti-linux-kernel-6.18.13+git-ti "$KBASE"
git -C "$KERNEL_SRC" tag ti-sdk-12.00.00.07.04-baseline "$KBASE"
clone_sdk ti-u-boot-sdk12 ti-u-boot-2026.01+git "$UBASE"
git -C "$UBOOT_SRC" tag ti-sdk-12.00.00.07.04-baseline "$UBASE"
git -C "$UBOOT_SRC" am "$ROOT/bsp/u-boot/patches/0002-am64x-evm-a53-set-bootdelay-to-5.patch"

FULLCHAIN="$WORKSPACE_ROOT/ti-u-boot-sdk12-sk-am64b-local-fullchain"
git -C "$UBOOT_SRC" worktree add -b migration-local-fullchain "$FULLCHAIN" "$UBASE"
git -C "$FULLCHAIN" am \
    "$ROOT/bsp/u-boot/patches/0001-am64x-rm-cfg-assign-mcu-gpio-router-to-main-0-r5-1.patch" \
    "$ROOT/bsp/u-boot/patches/0006-am64x-evm-a53-local-fullchain-bootdelay-10.patch"

clone_sdk trusted-firmware-a-2.14+git trusted-firmware-a-2.14+git "$TFA_HEAD" \
    https://git.trustedfirmware.org/TF-A/trusted-firmware-a.git
clone_sdk optee-os-4.9.0+git optee-os-4.9.0+git "$OPTEE_HEAD" \
    https://github.com/OP-TEE/optee_os.git

# This copy is local to the target, from its freshly installed MCU+ package.
# No installed source tree is transferred between hosts.
cp -a "$MCU_PLUS_SDK_INSTALL_ROOT" "$MCU_PLUS_SDK_PATH"
git -C "$MCU_PLUS_SDK_PATH" init -b main
git -C "$MCU_PLUS_SDK_PATH" add -A
git -C "$MCU_PLUS_SDK_PATH" commit -m 'baseline: import reinstalled mcu plus sdk 12.00.00.27'
git -C "$MCU_PLUS_SDK_PATH" tag ti-mcu-plus-sdk-12.00.00.27-baseline
git -C "$MCU_PLUS_SDK_PATH" switch -c phase2-tsn-c-case
git -C "$MCU_PLUS_SDK_PATH" am \
    "$ROOT/projects/tsn_c_case/patches/0001-tsn-add-remoteproc-gptp-icssg-project.patch" \
    "$ROOT/projects/tsn_c_case/patches/0002-tsn-trace-remoteproc-gptp-bridge-path.patch"
git clone --bare --no-hardlinks "$MCU_PLUS_SDK_PATH" "$SEED"
git -C "$MCU_PLUS_SDK_PATH" remote add origin "$SEED"

for name in ti-u-boot-sdk12 ti-u-boot-sdk12-sk-am64b-local-fullchain \
    ti-linux-kernel-sdk12 mcu_plus_sdk_am64x_12_00_00_27 \
    trusted-firmware-a-2.14+git optee-os-4.9.0+git; do
    dest="$WORKSPACE_ROOT/$name"
    [[ -z "$(git -C "$dest" status --porcelain)" ]]
    printf '[OK] %s %s\n' "$name" "$(git -C "$dest" rev-parse HEAD)"
done
bash "$ROOT/tools/prepare/verify-workspace-state.sh"
