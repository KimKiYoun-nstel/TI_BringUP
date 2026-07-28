#!/usr/bin/env bash
# Shared SK critical/background runner for the multiclass Qbv qualification.
set -u

RUN=${RUN:?}
SEQUENCE=${SEQUENCE:?}
DURATION_SEC=${DURATION_SEC:?}
BACKGROUND_RATE=${BACKGROUND_RATE:?}
SAMPLE_COUNT=${SAMPLE_COUNT:?}
RELEASE_PHASE_NS=${RELEASE_PHASE_NS:?}
ENQUEUE_ADVANCE_NS=${ENQUEUE_ADVANCE_NS:?}
TOOLS=/tmp/p2-qbv-on-tools

mkdir -p "$RUN"
pmc -u -b 0 'GET TIME_STATUS_NP' > "$RUN/ptp-health-before.txt" 2>&1
pmc -u -b 0 'GET PORT_DATA_SET' > "$RUN/ptp-port-before.txt" 2>&1
tc -s qdisc show dev eth0 > "$RUN/qos-before.txt"
ethtool -S eth0 > "$RUN/counters-before.txt"

sender_pid=
background_pid=

cancel() {
    [ -z "$sender_pid" ] || kill -TERM "$sender_pid" 2>/dev/null || true
    [ -z "$background_pid" ] || kill -TERM "$background_pid" 2>/dev/null || true
    [ -z "$sender_pid" ] || wait "$sender_pid" 2>/dev/null || true
    [ -z "$background_pid" ] || wait "$background_pid" 2>/dev/null || true
    printf 'cancelled\n' > "$RUN/done"
    printf 'state=cancelled sender_alive=0 background_alive=0\n' > "$RUN/progress.txt"
    exit 130
}
trap cancel INT TERM

BASE=$(phc_ctl /dev/ptp0 get | awk '/clock time/ {split($5,a,"."); printf "%.0f", (a[1]+3)*1000000000}')
iperf3 -c 10.33.0.2 -u -b "$BACKGROUND_RATE" -l 1472 -t $((DURATION_SEC + 10)) -p 5003 --json > "$RUN/background-client.json" 2>&1 &
background_pid=$!
sleep 1

started=$(date +%s)
P2_VLAN_PCP=2 P2_SCHED_FIFO_PRIORITY=80 "$TOOLS/p2_native_sender" eth0 "$SAMPLE_COUNT" "$SEQUENCE" 1000 "$RUN/sender.csv" "$BASE" "$RELEASE_PHASE_NS" 500000 "$ENQUEUE_ADVANCE_NS" > "$RUN/sender.log" 2>&1 &
sender_pid=$!
while kill -0 "$sender_pid" 2>/dev/null; do
    now=$(date +%s)
    if kill -0 "$background_pid" 2>/dev/null; then background_alive=1; else background_alive=0; fi
    printf 'state=running elapsed_sec=%s sender_alive=1 background_alive=%s updated_epoch=%s\n' \
        "$((now - started))" "$background_alive" "$now" > "$RUN/progress.txt"
    sleep 5
done
wait "$sender_pid"
sender_status=$?
wait "$background_pid"
background_status=$?

printf '%s\n' "$BASE" > "$RUN/base-time-ns.txt"
pmc -u -b 0 'GET TIME_STATUS_NP' > "$RUN/ptp-health-after.txt" 2>&1
pmc -u -b 0 'GET PORT_DATA_SET' > "$RUN/ptp-port-after.txt" 2>&1
tc -s qdisc show dev eth0 > "$RUN/qos-after.txt"
ethtool -S eth0 > "$RUN/counters-after.txt"

if [ "$sender_status" -eq 0 ] && [ "$background_status" -eq 0 ]; then
    printf 'passed\n' > "$RUN/done"
    printf 'state=passed elapsed_sec=%s sender_alive=0 background_alive=0\n' "$(( $(date +%s) - started ))" > "$RUN/progress.txt"
else
    printf 'failed sender=%s background=%s\n' "$sender_status" "$background_status" > "$RUN/done"
    printf 'state=failed sender=%s background=%s\n' "$sender_status" "$background_status" > "$RUN/progress.txt"
fi
