#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the target\n' >&2
    exit 1
fi

IFACE=${1:-}
if [[ -z "$IFACE" ]]; then
    printf 'usage: %s <iface>\n' "${0##*/}" >&2
    exit 1
fi

ROLE=${ROLE:-sender}
VLAN_ID=${VLAN_ID:-301}
VLAN_DEV=${VLAN_DEV:-${IFACE}.${VLAN_ID}}
LOCAL_CIDR=${LOCAL_CIDR:-10.31.0.1/24}
PORT_A=${PORT_A:-5001}
PORT_B=${PORT_B:-5002}
SET_TX_QUEUES=${SET_TX_QUEUES:-}
DISABLE_RROBIN=${DISABLE_RROBIN:-no}
RESET_ROOT_QDISC=${RESET_ROOT_QDISC:-yes}
RESET_VLAN=${RESET_VLAN:-yes}
SET_VLAN_EGRESS_MAP=${SET_VLAN_EGRESS_MAP:-no}
ADD_FILTERS=${ADD_FILTERS:-no}
LINK_WAIT_SEC=${LINK_WAIT_SEC:-3}
STOP_IPERF=${STOP_IPERF:-yes}

if [[ "$STOP_IPERF" == yes ]]; then
    pkill iperf3 2>/dev/null || true
fi

if [[ "$RESET_ROOT_QDISC" == yes ]]; then
    tc qdisc del dev "$IFACE" root 2>/dev/null || true
    tc qdisc del dev "$IFACE" clsact 2>/dev/null || true
fi

if [[ "$RESET_VLAN" == yes ]]; then
    ip link del "$VLAN_DEV" 2>/dev/null || true
fi

ip addr flush dev "$IFACE" 2>/dev/null || true
ip link set "$IFACE" down

if [[ -n "$SET_TX_QUEUES" ]]; then
    ethtool -L "$IFACE" tx "$SET_TX_QUEUES"
fi

if [[ "$DISABLE_RROBIN" == yes ]]; then
    ethtool --set-priv-flags "$IFACE" p0-rx-ptype-rrobin off
fi

ip link set "$IFACE" up
sleep "$LINK_WAIT_SEC"

ip link add link "$IFACE" name "$VLAN_DEV" type vlan id "$VLAN_ID"

if [[ "$SET_VLAN_EGRESS_MAP" == yes ]]; then
    ip link set "$VLAN_DEV" type vlan egress 0:0 1:1 2:2 3:3 4:4 5:5 6:6 7:7
fi

ip addr flush dev "$VLAN_DEV" 2>/dev/null || true
ip addr add "$LOCAL_CIDR" dev "$VLAN_DEV"
ip link set "$VLAN_DEV" up

if [[ "$ADD_FILTERS" == yes ]]; then
    tc qdisc add dev "$VLAN_DEV" clsact 2>/dev/null || true
    tc filter replace dev "$VLAN_DEV" egress protocol ip prio 1 u32 \
        match ip dport "$PORT_A" 0xffff \
        action skbedit priority 7
    tc filter replace dev "$VLAN_DEV" egress protocol ip prio 2 u32 \
        match ip dport "$PORT_B" 0xffff \
        action skbedit priority 6
fi

if [[ "$ROLE" == receiver ]]; then
    iperf3 -s -D -B "${LOCAL_CIDR%/*}" -p "$PORT_A"
    iperf3 -s -D -B "${LOCAL_CIDR%/*}" -p "$PORT_B"
fi

ethtool "$IFACE" | grep -E 'Speed|Duplex|Link detected' || true
ip -4 addr show dev "$VLAN_DEV"

if [[ "$ADD_FILTERS" == yes ]]; then
    tc -s filter show dev "$VLAN_DEV" egress || true
fi
