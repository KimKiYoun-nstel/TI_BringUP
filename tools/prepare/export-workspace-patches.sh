#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRINGUP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$BRINGUP_ROOT/tools/env/sdk-12.00.00.07.04.env"

usage() {
    cat <<'EOF'
Usage:
  ./tools/prepare/export-workspace-patches.sh <u-boot|linux> <patch-name>

Purpose:
  Export current workspace working-tree changes into Main Repo-managed patch storage.

Examples:
  ./tools/prepare/export-workspace-patches.sh u-boot 0002-my-change.patch
  ./tools/prepare/export-workspace-patches.sh linux 0003-my-change.patch
EOF
}

if [ "$#" -ne 2 ]; then
    usage >&2
    exit 1
fi

component="$1"
patch_name="$2"

case "$component" in
    u-boot)
        workspace="$UBOOT_SRC"
        output_dir="$BRINGUP_ROOT/bsp/u-boot/patches"
        ;;
    linux)
        workspace="$KERNEL_SRC"
        output_dir="$BRINGUP_ROOT/bsp/linux/patches"
        ;;
    *)
        echo "[ERROR] Unsupported component: $component" >&2
        usage >&2
        exit 1
        ;;
esac

if [ ! -d "$workspace/.git" ]; then
    echo "[ERROR] Workspace is missing or not a git repo: $workspace" >&2
    exit 1
fi

mkdir -p "$output_dir"
output_path="$output_dir/$patch_name"

if [ -e "$output_path" ]; then
    echo "[ERROR] Patch already exists: $output_path" >&2
    exit 1
fi

if git -C "$workspace" diff --quiet; then
    echo "[ERROR] No working-tree diff to export from $workspace" >&2
    exit 1
fi

git -C "$workspace" diff --binary > "$output_path"

if [ ! -s "$output_path" ]; then
    echo "[ERROR] Exported patch is empty: $output_path" >&2
    rm -f "$output_path"
    exit 1
fi

printf '[INFO] Exported %s workspace diff to %s\n' "$component" "$output_path"
printf '[INFO] Review and register the patch in the matching series file before replaying it.\n'
