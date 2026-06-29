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

TAPRIO_MODE=${TAPRIO_MODE:-sw}
HANDLE=${HANDLE:-200:}
NUM_TC=${NUM_TC:-3}
MAP_SPEC=${MAP_SPEC:-0 0 1 2 0 0 0 0 0 0 0 0 0 0 0 0}
QUEUES_SPEC=${QUEUES_SPEC:-1@0 1@1 1@2}
BASE_TIME=${BASE_TIME:-0}
CLOCKID=${CLOCKID:-CLOCK_TAI}
SCHED_ENTRIES=${SCHED_ENTRIES:-05 250000;03 250000}

read -r -a map_arr <<< "$MAP_SPEC"
read -r -a queues_arr <<< "$QUEUES_SPEC"
IFS=';' read -r -a entries <<< "$SCHED_ENTRIES"

cmd=(tc qdisc replace dev "$IFACE" root handle "$HANDLE" taprio)
cmd+=(num_tc "$NUM_TC")
cmd+=(map "${map_arr[@]}")
cmd+=(queues "${queues_arr[@]}")
cmd+=(base-time "$BASE_TIME")

for entry in "${entries[@]}"; do
    read -r mask interval <<< "$entry"
    cmd+=(sched-entry S "$mask" "$interval")
done

case "$TAPRIO_MODE" in
    hw)
        cmd+=(flags 2)
        ;;
    sw)
        cmd+=(clockid "$CLOCKID")
        ;;
    *)
        printf 'unsupported TAPRIO_MODE=%s\n' "$TAPRIO_MODE" >&2
        exit 1
        ;;
esac

"${cmd[@]}"
tc -s qdisc show dev "$IFACE"
