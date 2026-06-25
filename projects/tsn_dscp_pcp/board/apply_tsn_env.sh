#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
TMDS_IP=${TMDS_IP:-192.168.0.220}
SK_IP=${SK_IP:-10.50.0.2}
TMDS_USER=${TMDS_USER:-root}
SK_USER=${SK_USER:-root}

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SK_SSH_OPTS=(-o ProxyJump=${TMDS_USER}@${TMDS_IP} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

TMDS_OVERLAY="$ROOT_DIR/rootfs/overlays/tmds64evm-tsn-dscp-pcp"
SK_OVERLAY="$ROOT_DIR/rootfs/overlays/sk-am64b-tsn-dscp-pcp"

printf '==> Deploy TMDS overlay\n'
tar -C "$TMDS_OVERLAY" -cf - . | ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" 'tar -xf - -C /'

printf '==> Enable TMDS boot-time apply service\n'
ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" 'systemctl daemon-reload && systemctl enable ti-tsn-dscp-pcp-tmds.service'

printf '==> Apply TMDS network profile\n'
ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" '/bin/sh /usr/local/sbin/ti-tsn-dscp-pcp-tmds-apply.sh'

printf '==> Deploy SK overlay\n'
tar -C "$SK_OVERLAY" -cf - . | ssh "${SK_SSH_OPTS[@]}" "${SK_USER}@${SK_IP}" 'tar -xf - -C /'

printf '==> Enable SK boot-time apply service\n'
ssh "${SK_SSH_OPTS[@]}" "${SK_USER}@${SK_IP}" 'systemctl daemon-reload && systemctl enable ti-tsn-dscp-pcp-sk.service'

printf '==> Apply SK network profile\n'
ssh "${SK_SSH_OPTS[@]}" "${SK_USER}@${SK_IP}" '/bin/sh /usr/local/sbin/ti-tsn-dscp-pcp-sk-apply.sh' || true

printf '==> Probe SK reconnect\n'
for _ in $(seq 1 15); do
    if ssh "${SK_SSH_OPTS[@]}" "${SK_USER}@${SK_IP}" 'ip -br addr show dev br-tsn' 2>/dev/null; then
        exit 0
    fi
    sleep 2
done

printf 'SK reconnect probe failed\n' >&2
exit 1
