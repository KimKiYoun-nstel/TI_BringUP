#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the SK target\n' >&2
    exit 1
fi

IFACE=${1:-eth1}
VLAN_ID=${VLAN_ID:-301}
VLAN_DEV=${VLAN_DEV:-${IFACE}.${VLAN_ID}}
LOCAL_CIDR=${LOCAL_CIDR:-10.31.0.1/24}
MAP_SPEC=${MAP_SPEC:-0 0 0 0 0 0 1 2 0 0 0 0 0 0 0 0}
QUEUES_SPEC=${QUEUES_SPEC:-1@0 1@1 1@2}
PORT_P7=${PORT_P7:-5001}
PORT_P6=${PORT_P6:-5002}
BASE_TIME=${BASE_TIME:-$(( $(date +%s%N) + 5000000000 ))}
INTERVAL_NS=${INTERVAL_NS:-50000000}
GPTP_CFG=${GPTP_CFG:-/tmp/gptp-endpoint-qbv.cfg}

printf '==> Prepare SK A4 coexist state on %s (%s)\n' "$IFACE" "$VLAN_DEV"

pkill ptp4l 2>/dev/null || true
pkill phc2sys 2>/dev/null || true

tc qdisc del dev "$IFACE" root 2>/dev/null || true
tc qdisc del dev "$IFACE" clsact 2>/dev/null || true
ip link del "$VLAN_DEV" 2>/dev/null || true
ip addr flush dev "$IFACE"
ip link set "$IFACE" up

ethtool --set-priv-flags "$IFACE" p0-rx-ptype-rrobin off || true

ip link add link "$IFACE" name "$VLAN_DEV" type vlan id "$VLAN_ID"
ip link set "$VLAN_DEV" type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
ip addr add "$LOCAL_CIDR" dev "$VLAN_DEV"
ip link set "$VLAN_DEV" up

tc qdisc add dev "$VLAN_DEV" clsact
tc filter add dev "$VLAN_DEV" egress protocol ip prio 1 u32 \
    match ip dport "$PORT_P7" 0xffff \
    action skbedit priority 7
tc filter add dev "$VLAN_DEV" egress protocol ip prio 2 u32 \
    match ip dport "$PORT_P6" 0xffff \
    action skbedit priority 6

tc qdisc replace dev "$IFACE" root handle 200: taprio \
    num_tc 3 \
    map $MAP_SPEC \
    queues $QUEUES_SPEC \
    base-time "$BASE_TIME" \
    sched-entry S 05 "$INTERVAL_NS" \
    sched-entry S 03 "$INTERVAL_NS" \
    clockid CLOCK_TAI

printf '%s\n' \
    '[global]' \
    'network_transport L2' \
    'delay_mechanism P2P' \
    'time_stamping hardware' \
    'twoStepFlag 1' \
    'summary_interval 1' \
    'logging_level 6' \
    'tx_timestamp_timeout 100' > "$GPTP_CFG"

ip -4 addr show dev "$VLAN_DEV"
tc -s qdisc show dev "$IFACE"
printf '==> gPTP config written to %s\n' "$GPTP_CFG"
