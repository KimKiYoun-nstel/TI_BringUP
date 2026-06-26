#!/usr/bin/env bash
set -euo pipefail

TMDS_IP=${TMDS_IP:-192.168.0.220}
TMDS_USER=${TMDS_USER:-root}

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

ssh "${SSH_OPTS[@]}" "${TMDS_USER}@${TMDS_IP}" <<'EOF'
set -euo pipefail

pkill tcpdump 2>/dev/null || true
pkill iperf3 2>/dev/null || true

ip netns del ep1 2>/dev/null || true
ip netns del ep2 2>/dev/null || true

ip link del eth1.300 2>/dev/null || true
ip link del eth2.301 2>/dev/null || true

ip netns add ep1
ip netns add ep2

ip link set eth1 down
ip link set eth2 down
ip link set eth1 netns ep1
ip link set eth2 netns ep2

ip -n ep1 link set lo up
ip -n ep2 link set lo up

ip -n ep1 link set eth1 up
ip -n ep2 link set eth2 up

ip -n ep1 link add link eth1 name eth1.301 type vlan id 301
ip -n ep2 link add link eth2 name eth2.301 type vlan id 301

ip -n ep1 addr replace 10.31.0.2/24 dev eth1.301
ip -n ep2 addr replace 10.31.0.1/24 dev eth2.301

ip -n ep2 link set eth2.301 type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7

ip -n ep1 link set eth1.301 up
ip -n ep2 link set eth2.301 up

ip netns exec ep2 tc qdisc del dev eth2.301 clsact 2>/dev/null || true
ip netns exec ep2 tc qdisc add dev eth2.301 clsact
ip netns exec ep2 tc filter add dev eth2.301 egress protocol ip prio 1 u32 \
  match ip dport 5001 0xffff \
  action skbedit priority 7
ip netns exec ep2 tc filter add dev eth2.301 egress protocol ip prio 2 u32 \
  match ip dport 5002 0xffff \
  action skbedit priority 6

ip netns exec ep1 iperf3 -s -D -p 5001
ip netns exec ep1 iperf3 -s -D -p 5002

printf '%s\n' '=== ep1 ==='
ip -n ep1 -br addr
printf '%s\n' '=== ep2 ==='
ip -n ep2 -br addr
printf '%s\n' '=== ep2 filters ==='
ip netns exec ep2 tc -s filter show dev eth2.301 egress
printf '%s\n' '=== ep2 ping ==='
ip netns exec ep2 ping -c 2 -I eth2.301 10.31.0.2
EOF

printf 'TMDS Test B namespace setup complete on %s\n' "$TMDS_IP"
