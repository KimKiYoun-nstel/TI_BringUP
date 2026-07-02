#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(git rev-parse --show-toplevel)
TMDS_IP=${TMDS_IP:-192.168.0.220}
TMDS_USER=${TMDS_USER:-root}
OUT_DIR="$ROOT_DIR/projects/tsn_c_case/logs"
STAMP=$(date +%F_%H%M%S)
OUT_FILE="$OUT_DIR/${STAMP}_tmds_c1_linux_baseline.txt"

mkdir -p "$OUT_DIR"

SSH_OPTS=(
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
)

ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" <<'EOF' | tee "$OUT_FILE"
set -euo pipefail

printf '===== uname -a =====\n'
uname -a

printf '\n===== model =====\n'
cat /proc/device-tree/model 2>/dev/null || true

printf '\n===== compatible =====\n'
strings /proc/device-tree/compatible 2>/dev/null || true

printf '\n===== overlays in boot =====\n'
fw_printenv name_overlays 2>/dev/null || true

printf '\n===== ip -br link =====\n'
ip -br link

printf '\n===== ip -br addr =====\n'
ip -br addr

for dev in eth0 eth1 eth2; do
  printf '\n===== ethtool -i %s =====\n' "$dev"
  ethtool -i "$dev" 2>/dev/null || true
done

for dev in eth1 eth2; do
  printf '\n===== ethtool -T %s =====\n' "$dev"
  ethtool -T "$dev" 2>/dev/null || true
done

printf '\n===== /sys/class/ptp =====\n'
for p in /sys/class/ptp/ptp*; do
  [ -e "$p" ] || continue
  printf -- '--- %s ---\n' "$p"
  cat "$p/clock_name" 2>/dev/null || true
  readlink -f "$p/device" 2>/dev/null || true
done

printf '\n===== remoteproc =====\n'
for r in /sys/class/remoteproc/remoteproc*; do
  [ -e "$r" ] || continue
  printf -- '--- %s ---\n' "$r"
  cat "$r/name" 2>/dev/null || true
  cat "$r/state" 2>/dev/null || true
  cat "$r/firmware" 2>/dev/null || true
done

printf '\n===== dmesg icssg/prueth/phy/remoteproc/firmware =====\n'
dmesg | grep -iE 'icssg|prueth|iep|mdio|phy|remoteproc|firmware' | tail -n 300
EOF

printf '\nSaved baseline log: %s\n' "$OUT_FILE"
