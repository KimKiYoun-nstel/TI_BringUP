#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
TMDS_IP=${TMDS_IP:-192.168.0.220}
TMDS_USER=${TMDS_USER:-root}
REAPPLY_BASELINE=${REAPPLY_BASELINE:-1}

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

printf '==> Stop TMDS test processes and remove temporary namespaces\n'
ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" <<'EOF'
set -euo pipefail

pkill tcpdump 2>/dev/null || true
pkill iperf3 2>/dev/null || true

ip netns del ep1 2>/dev/null || true
ip netns del ep2 2>/dev/null || true

ip link del eth1.301 2>/dev/null || true
ip link del eth2.301 2>/dev/null || true
EOF

if [[ "$REAPPLY_BASELINE" == "1" ]]; then
    printf '==> Reapply baseline topology\n'
    bash "$ROOT_DIR/projects/tsn_qbv/board/setup_sk_switchdev_base.sh"
fi
