#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
TMDS_HELPER="$ROOT_DIR/projects/tsn_dscp_pcp/board/setup_testb_tmds_netns.sh"

if [[ ! -f "$TMDS_HELPER" ]]; then
    printf 'missing TMDS helper: %s\n' "$TMDS_HELPER" >&2
    exit 1
fi

printf '==> Recreate TMDS endpoint namespaces from validated Test B helper\n'
bash "$TMDS_HELPER"
