#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
BASELINE_APPLY="$ROOT_DIR/projects/tsn_dscp_pcp/board/apply_tsn_env.sh"

if [[ ! -f "$BASELINE_APPLY" ]]; then
    printf 'missing baseline helper: %s\n' "$BASELINE_APPLY" >&2
    exit 1
fi

printf '==> Reapply shared TSN baseline from tsn_dscp_pcp\n'
bash "$BASELINE_APPLY"

printf '\n==> Next checks on SK over UART\n'
printf '  %s\n' 'devlink dev param show platform/8000000.ethernet'
printf '  %s\n' 'bridge -d vlan show'
printf '  %s\n' 'bridge link'
printf '  %s\n' 'ethtool --show-priv-flags eth0'
printf '  %s\n' 'ethtool --show-priv-flags eth1'
printf '  %s\n' 'tc -s qdisc show dev eth0'
printf '  %s\n' 'tc -s qdisc show dev eth1'
