#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf 'run as root on the target board\n' >&2
    exit 1
fi

IFACE=${1:-eth0}
HANDLE=${HANDLE:-100:}
NUM_TC=${NUM_TC:-3}
BASE_TIME=${BASE_TIME:-}
FLAGS=${FLAGS:-0}
HIGH_GATE_MASK=${HIGH_GATE_MASK:-0x4}
LOW_GATE_MASK=${LOW_GATE_MASK:-0x3}
HIGH_INTERVAL_NS=${HIGH_INTERVAL_NS:-50000000}
LOW_INTERVAL_NS=${LOW_INTERVAL_NS:-50000000}
MAP=(2 2 1 0 2 2 2 2 2 2 2 2 2 2 2 2)
QUEUES=(1@0 1@1 2@2)

if [[ -z "$BASE_TIME" ]]; then
    printf 'set BASE_TIME to a future PHC or system time value before running setup_taprio.sh\n' >&2
    exit 1
fi

printf '==> Apply taprio on %s\n' "$IFACE"
printf '    high gate mask=%s interval=%s ns\n' "$HIGH_GATE_MASK" "$HIGH_INTERVAL_NS"
printf '    low gate mask=%s interval=%s ns\n' "$LOW_GATE_MASK" "$LOW_INTERVAL_NS"

tc qdisc replace dev "$IFACE" root handle "$HANDLE" taprio \
    num_tc "$NUM_TC" \
    map "${MAP[@]}" \
    queues "${QUEUES[@]}" \
    base-time "$BASE_TIME" \
    sched-entry S "$HIGH_GATE_MASK" "$HIGH_INTERVAL_NS" \
    sched-entry S "$LOW_GATE_MASK" "$LOW_INTERVAL_NS" \
    flags "$FLAGS"

printf '==> Active qdisc on %s\n' "$IFACE"
tc qdisc show dev "$IFACE"
tc -s qdisc show dev "$IFACE"
