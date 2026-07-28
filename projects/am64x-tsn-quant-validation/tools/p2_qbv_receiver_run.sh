#!/usr/bin/env bash
# Shared TMDS critical/background runner for the multiclass Qbv qualification.
set -u

RUN=${RUN:?}
SEQUENCE=${SEQUENCE:?}
TIMEOUT_SEC=${TIMEOUT_SEC:?}
SAMPLE_COUNT=${SAMPLE_COUNT:?}
TOOLS=/tmp/p2-qbv-on-tools

mkdir -p "$RUN"
pmc -u -b 0 'GET TIME_STATUS_NP' > "$RUN/ptp-health-before.txt" 2>&1
pmc -u -b 0 'GET PORT_DATA_SET' > "$RUN/ptp-port-before.txt" 2>&1
tc -s qdisc show dev eth1 > "$RUN/qos-before.txt"
ethtool -S eth1 > "$RUN/counters-before.txt"

receiver_pid=
server_pid=

cancel() {
    [ -z "$receiver_pid" ] || kill -TERM "$receiver_pid" 2>/dev/null || true
    [ -z "$server_pid" ] || kill -TERM "$server_pid" 2>/dev/null || true
    [ -z "$receiver_pid" ] || wait "$receiver_pid" 2>/dev/null || true
    [ -z "$server_pid" ] || wait "$server_pid" 2>/dev/null || true
    printf 'cancelled\n' > "$RUN/done"
    printf 'state=cancelled receiver_alive=0 server_alive=0\n' > "$RUN/progress.txt"
    exit 130
}
trap cancel INT TERM

iperf3 -s -1 -B 10.33.0.2 -p 5003 --json > "$RUN/background-server.json" 2>&1 &
server_pid=$!
started=$(date +%s)
python3 "$TOOLS/p2_ptp_l2_hwts_probe.py" recv --iface eth1 --count "$SAMPLE_COUNT" --start-seq "$SEQUENCE" \
    --timeout-sec "$TIMEOUT_SEC" --vlan-id 311 --pcp 2 --socket-priority 3 --frame-size 128 \
    --csv "$RUN/receiver.csv" > "$RUN/receiver.log" 2>&1 &
receiver_pid=$!

while kill -0 "$receiver_pid" 2>/dev/null; do
    now=$(date +%s)
    if kill -0 "$server_pid" 2>/dev/null; then server_alive=1; else server_alive=0; fi
    printf 'state=running elapsed_sec=%s receiver_alive=1 server_alive=%s updated_epoch=%s\n' \
        "$((now - started))" "$server_alive" "$now" > "$RUN/progress.txt"
    sleep 5
done
wait "$receiver_pid"
receiver_status=$?
wait "$server_pid"
server_status=$?

if [ "$receiver_status" -eq 0 ] && [ "$server_status" -eq 0 ]; then
    printf 'passed\n' > "$RUN/done"
    printf 'state=passed elapsed_sec=%s receiver_alive=0 server_alive=0\n' "$(( $(date +%s) - started ))" > "$RUN/progress.txt"
else
    printf 'failed receiver=%s server=%s\n' "$receiver_status" "$server_status" > "$RUN/done"
    printf 'state=failed receiver=%s server=%s\n' "$receiver_status" "$server_status" > "$RUN/progress.txt"
fi
