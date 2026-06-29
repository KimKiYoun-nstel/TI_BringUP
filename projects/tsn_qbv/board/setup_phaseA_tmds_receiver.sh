#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the TMDS target\n' >&2
    exit 1
fi

IFACE=${1:-eth2}
VLAN_ID=${VLAN_ID:-301}
VLAN_DEV=${VLAN_DEV:-${IFACE}.${VLAN_ID}}
LOCAL_CIDR=${LOCAL_CIDR:-10.31.0.2/24}
PORT_A=${PORT_A:-5001}
PORT_B=${PORT_B:-5002}

printf '==> Prepare TMDS receiver on %s (%s)\n' "$IFACE" "$VLAN_DEV"

pkill ptp4l 2>/dev/null || true
pkill phc2sys 2>/dev/null || true
pkill iperf3 2>/dev/null || true

tc qdisc del dev "$IFACE" root 2>/dev/null || true
tc qdisc del dev "$IFACE" clsact 2>/dev/null || true

ip link del "$VLAN_DEV" 2>/dev/null || true
ip addr flush dev "$IFACE"
ip link set "$IFACE" up

ip link add link "$IFACE" name "$VLAN_DEV" type vlan id "$VLAN_ID"
ip addr add "$LOCAL_CIDR" dev "$VLAN_DEV"
ip link set "$VLAN_DEV" up

iperf3 -s -D -B "${LOCAL_CIDR%/*}" -p "$PORT_A"
iperf3 -s -D -B "${LOCAL_CIDR%/*}" -p "$PORT_B"

ip -4 addr show dev "$VLAN_DEV"
pgrep -a iperf3 || true
