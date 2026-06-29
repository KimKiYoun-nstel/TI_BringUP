#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the target board\n' >&2
    exit 1
fi

IFACE=${1:-eth0}
HANDLE=${HANDLE:-100:}
NUM_TC=${NUM_TC:-3}
MAP_SPEC=${MAP_SPEC:-2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2}
QUEUES_SPEC=${QUEUES_SPEC:-1@0 1@1 2@2}

if [[ "$MAP_SPEC" == "2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2" ]]; then
    printf '%s\n' 'note: current default map is the validated baseline map.'
    printf '%s\n' '      it preserves PCP on wire, but it does not separate p0/p6/p7 into different TCs.'
    printf '%s\n' '      for Phase 1 mapping work, override MAP_SPEC and QUEUES_SPEC explicitly.'
fi

printf '==> Disable p0-rx-ptype-rrobin on %s\n' "$IFACE"
ethtool --set-priv-flags "$IFACE" p0-rx-ptype-rrobin off

printf '==> Apply mqprio hw 1 mode channel on %s\n' "$IFACE"
tc qdisc replace dev "$IFACE" root handle "$HANDLE" mqprio \
    num_tc "$NUM_TC" \
    map $MAP_SPEC \
    queues $QUEUES_SPEC \
    hw 1 mode channel

printf '==> Active qdisc on %s\n' "$IFACE"
tc qdisc show dev "$IFACE"
tc -s qdisc show dev "$IFACE"
